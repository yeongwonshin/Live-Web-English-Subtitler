from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time

from .audio import AudioConfig, list_devices_text, make_capture
from .overlay import SubtitleOverlay
from .transcriber import WhisperWorker


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="autosub",
        description="Generate live English subtitles from system/browser audio without uploading video files.",
    )
    parser.add_argument("--source", default="auto", help="Audio source/device keyword. Use auto for default loopback/monitor.")
    parser.add_argument("--list-devices", action="store_true", help="List available audio devices and exit.")
    parser.add_argument("--model", default="base.en", help="faster-whisper model name, e.g. tiny.en, base.en, small.en")
    parser.add_argument("--language", default="en", help="Speech language code. Default: en")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"], help="Whisper device")
    parser.add_argument("--compute-type", default="int8", help="faster-whisper compute type, e.g. int8, float16")
    parser.add_argument("--beam-size", type=int, default=1, help="Beam size for transcription; 1 is fastest for live captions")
    parser.add_argument("--silence-rms", type=float, default=0.004, help="RMS threshold for audio activity")
    parser.add_argument("--min-chunk-seconds", type=float, default=0.65, help="Minimum speech chunk duration")
    parser.add_argument("--max-chunk-seconds", type=float, default=1.8, help="Maximum speech chunk duration before transcription")
    parser.add_argument("--silence-hold-seconds", type=float, default=0.25, help="Silence duration required to close a chunk")
    parser.add_argument("--partial-chunk-seconds", type=float, default=1.0, help="Emit rolling live chunks this often while speech continues; lower means lower latency")
    parser.add_argument("--partial-overlap-seconds", type=float, default=0.25, help="Audio overlap kept between rolling chunks to avoid cutting words")
    parser.add_argument("--transcriber-queue-size", type=int, default=2, help="Maximum pending chunks; lower keeps captions fresher")
    parser.add_argument("--no-vad-filter", action="store_true", help="Disable faster-whisper VAD for lower latency on already chunked audio")
    parser.add_argument("--subtitle-ttl", type=float, default=6.0, help="Seconds a subtitle remains visible")
    parser.add_argument("--no-overlay", action="store_true", help="Disable subtitle overlay; captions will be printed to the console instead")
    parser.add_argument("--print-captions", action="store_true", help="Debug only: also print recognized captions to the terminal")
    parser.add_argument("--quiet", action="store_true", help="Suppress status logs. Captions still appear in the overlay unless --no-overlay is set")
    parser.add_argument("--show-levels", action="store_true", help="Print live input RMS levels so you can verify that audio is reaching the program")
    parser.add_argument("--allow-mic-fallback", action="store_true", help="On macOS, allow auto mode to use the microphone if no BlackHole/loopback input is found")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.list_devices:
        print(list_devices_text())
        return 0

    # Make src-layout imports work when launched directly from checkout.
    project_src = os.path.join(os.getcwd(), "src")
    if project_src not in sys.path:
        sys.path.insert(0, project_src)

    stop_requested = threading.Event()
    capture_holder = {"capture": None}
    worker_holder = {"worker": None}

    def status(text: str) -> None:
        if not args.quiet:
            print(text, flush=True)

    def request_stop() -> None:
        stop_requested.set()
        capture = capture_holder.get("capture")
        worker = worker_holder.get("worker")
        if capture is not None:
            try:
                capture.stop()
            except Exception:
                pass
        if worker is not None:
            try:
                worker.stop()
            except Exception:
                pass

    overlay = None if args.no_overlay else SubtitleOverlay(ttl=args.subtitle_ttl, on_close=request_stop)

    def caption(text: str) -> None:
        """Send real subtitle text to the overlay.

        Normal user mode must not print subtitles in the terminal. Terminal captions are enabled
        only when the user explicitly passes --print-captions or disables the overlay with --no-overlay.
        """
        if overlay:
            overlay.show(text)
        if args.no_overlay or args.print_captions:
            print(text, flush=True)

    status("Live Web English Subtitler is starting. Captions will appear only in the overlay window.")

    worker = WhisperWorker(
        model_name=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        on_text=caption,
        on_status=status,
        beam_size=args.beam_size,
        queue_size=args.transcriber_queue_size,
        vad_filter=not args.no_vad_filter,
    )
    worker_holder["worker"] = worker
    worker.start()

    cfg = AudioConfig(
        source=args.source,
        silence_rms=args.silence_rms,
        min_chunk_seconds=args.min_chunk_seconds,
        max_chunk_seconds=args.max_chunk_seconds,
        silence_hold_seconds=args.silence_hold_seconds,
        partial_chunk_seconds=args.partial_chunk_seconds,
        partial_overlap_seconds=args.partial_overlap_seconds,
        show_levels=args.show_levels,
        allow_mic_fallback=args.allow_mic_fallback,
    )
    capture = make_capture(cfg, on_chunk=worker.submit, on_status=lambda s: status(f"[audio] {s}"))
    capture_holder["capture"] = capture

    def audio_thread() -> None:
        try:
            capture.run()
        except Exception as exc:
            status(f"[audio capture failed] {exc}")

    thread = threading.Thread(target=audio_thread, daemon=True)
    thread.start()

    def stop_handler(signum, frame):
        request_stop()
        try:
            if overlay and overlay._root is not None:
                overlay._root.after(0, overlay._root.destroy)
        except Exception:
            pass

    try:
        signal.signal(signal.SIGINT, stop_handler)
        signal.signal(signal.SIGTERM, stop_handler)
    except Exception:
        pass

    if overlay:
        overlay.run()
    else:
        try:
            while not stop_requested.is_set():
                time.sleep(0.2)
        except KeyboardInterrupt:
            pass

    request_stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
