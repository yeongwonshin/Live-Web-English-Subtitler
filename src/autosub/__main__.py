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
    parser.add_argument("--beam-size", type=int, default=3, help="Beam size for transcription")
    parser.add_argument("--silence-rms", type=float, default=0.008, help="RMS threshold for audio activity")
    parser.add_argument("--min-chunk-seconds", type=float, default=1.8, help="Minimum speech chunk duration")
    parser.add_argument("--max-chunk-seconds", type=float, default=5.0, help="Maximum speech chunk duration before transcription")
    parser.add_argument("--silence-hold-seconds", type=float, default=0.65, help="Silence duration required to close a chunk")
    parser.add_argument("--subtitle-ttl", type=float, default=6.0, help="Seconds a subtitle remains visible")
    parser.add_argument("--no-overlay", action="store_true", help="Print captions to console only")
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

    overlay = None if args.no_overlay else SubtitleOverlay(ttl=args.subtitle_ttl)

    def emit(text: str) -> None:
        print(text, flush=True)
        if overlay:
            overlay.show(text)

    emit("Live Web English Subtitler is starting. Play an English web video; captions will appear when audio is detected.")

    worker = WhisperWorker(
        model_name=args.model,
        language=args.language,
        device=args.device,
        compute_type=args.compute_type,
        on_text=emit,
        beam_size=args.beam_size,
    )
    worker.start()

    cfg = AudioConfig(
        source=args.source,
        silence_rms=args.silence_rms,
        min_chunk_seconds=args.min_chunk_seconds,
        max_chunk_seconds=args.max_chunk_seconds,
        silence_hold_seconds=args.silence_hold_seconds,
    )
    capture = make_capture(cfg, on_chunk=worker.submit, on_status=lambda s: emit(f"[audio] {s}"))

    def audio_thread() -> None:
        try:
            capture.run()
        except Exception as exc:
            emit(f"[audio capture failed] {exc}")

    thread = threading.Thread(target=audio_thread, daemon=True)
    thread.start()

    stop_requested = threading.Event()

    def stop_handler(signum, frame):
        stop_requested.set()
        capture.stop()
        worker.stop()
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

    capture.stop()
    worker.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
