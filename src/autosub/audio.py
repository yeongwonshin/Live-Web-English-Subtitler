from __future__ import annotations

import platform
import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np

from .utils import resample_linear, rms_float32, to_mono_float32


@dataclass
class AudioConfig:
    source: str = "auto"
    target_rate: int = 16000
    block_ms: int = 120
    silence_rms: float = 0.008
    min_chunk_seconds: float = 1.8
    max_chunk_seconds: float = 5.0
    silence_hold_seconds: float = 0.65


class SpeechChunker:
    """Turns continuous mono 16 kHz audio into speech-like chunks."""

    def __init__(self, cfg: AudioConfig, on_chunk: Callable[[np.ndarray], None], on_level: Callable[[float], None] | None = None):
        self.cfg = cfg
        self.on_chunk = on_chunk
        self.on_level = on_level or (lambda _level: None)
        self._buf: list[np.ndarray] = []
        self._active = False
        self._last_sound = 0.0
        self._start_time = 0.0
        self._sample_count = 0

    def accept(self, audio_16k: np.ndarray) -> None:
        if audio_16k.size == 0:
            return
        level = rms_float32(audio_16k)
        self.on_level(level)
        now = time.time()
        is_sound = level >= self.cfg.silence_rms

        if is_sound and not self._active:
            self._active = True
            self._start_time = now
            self._buf = []
            self._sample_count = 0

        if self._active:
            self._buf.append(audio_16k)
            self._sample_count += audio_16k.size
            if is_sound:
                self._last_sound = now

            elapsed = self._sample_count / float(self.cfg.target_rate)
            silence_elapsed = now - self._last_sound if self._last_sound else 0.0
            should_flush_for_silence = elapsed >= self.cfg.min_chunk_seconds and silence_elapsed >= self.cfg.silence_hold_seconds
            should_flush_for_length = elapsed >= self.cfg.max_chunk_seconds
            if should_flush_for_silence or should_flush_for_length:
                self._flush()

    def _flush(self) -> None:
        if not self._buf:
            self._active = False
            return
        chunk = np.concatenate(self._buf).astype(np.float32)
        self._buf = []
        self._active = False
        self._sample_count = 0
        self._start_time = 0.0
        self._last_sound = 0.0
        if chunk.size >= int(self.cfg.min_chunk_seconds * self.cfg.target_rate * 0.6):
            self.on_chunk(chunk)


class AudioCaptureBase:
    def run(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class WindowsLoopbackCapture(AudioCaptureBase):
    """Windows WASAPI loopback capture using PyAudioWPatch."""

    def __init__(self, cfg: AudioConfig, on_chunk: Callable[[np.ndarray], None], on_status: Callable[[str], None] | None = None):
        self.cfg = cfg
        self.on_status = on_status or print
        self.chunker = SpeechChunker(cfg, on_chunk)
        self._stop = threading.Event()

    def run(self) -> None:
        try:
            import pyaudiowpatch as pyaudio
        except Exception as exc:
            raise RuntimeError("Windows loopback capture requires pyaudiowpatch. Install requirements-windows.txt") from exc

        pa = pyaudio.PyAudio()
        try:
            device = self._select_loopback_device(pa)
            rate = int(device.get("defaultSampleRate") or 48000)
            channels = int(device.get("maxInputChannels") or device.get("maxOutputChannels") or 2)
            channels = max(1, min(channels, 2))
            block = max(256, int(rate * self.cfg.block_ms / 1000.0))

            self.on_status(f"Capturing system audio: {device['name']} @ {rate}Hz")
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=channels,
                rate=rate,
                input=True,
                input_device_index=int(device["index"]),
                frames_per_buffer=block,
            )
            try:
                while not self._stop.is_set():
                    raw = stream.read(block, exception_on_overflow=False)
                    audio = np.frombuffer(raw, dtype=np.int16)
                    if channels > 1:
                        audio = audio.reshape(-1, channels)
                    mono = to_mono_float32(audio)
                    mono16 = resample_linear(mono, rate, self.cfg.target_rate)
                    self.chunker.accept(mono16)
            finally:
                stream.stop_stream()
                stream.close()
        finally:
            pa.terminate()

    def stop(self) -> None:
        self._stop.set()

    def _select_loopback_device(self, pa):
        devices = []
        default_speaker = None
        try:
            default_speaker = pa.get_default_wasapi_loopback()
        except Exception:
            default_speaker = None

        for i in range(pa.get_device_count()):
            dev = pa.get_device_info_by_index(i)
            name = str(dev.get("name", ""))
            is_loopback = dev.get("isLoopbackDevice") or "loopback" in name.lower()
            if is_loopback:
                devices.append(dev)

        source = self.cfg.source.lower().strip()
        if source != "auto":
            for dev in devices:
                if source in str(dev.get("name", "")).lower():
                    return dev
            raise RuntimeError(f"No Windows loopback device matching source={self.cfg.source!r}")

        if default_speaker is not None:
            return default_speaker
        if devices:
            return devices[0]
        raise RuntimeError("No WASAPI loopback device found. Check your Windows audio output device.")


class SoundDeviceCapture(AudioCaptureBase):
    """Generic capture using sounddevice. On Linux choose a Pulse/PipeWire monitor input; on macOS use a loopback device."""

    def __init__(self, cfg: AudioConfig, on_chunk: Callable[[np.ndarray], None], on_status: Callable[[str], None] | None = None):
        self.cfg = cfg
        self.on_status = on_status or print
        self.chunker = SpeechChunker(cfg, on_chunk)
        self._stop = threading.Event()
        self._q: queue.Queue[np.ndarray] = queue.Queue(maxsize=64)

    def run(self) -> None:
        try:
            import sounddevice as sd
        except Exception as exc:
            raise RuntimeError("Generic capture requires sounddevice. Install requirements-linux-mac.txt") from exc

        device_idx, samplerate, channels = self._select_device(sd)
        blocksize = max(256, int(samplerate * self.cfg.block_ms / 1000.0))
        self.on_status(f"Capturing input device: {device_idx} @ {samplerate}Hz")

        def callback(indata, frames, time_info, status):
            if status:
                # Keep running; overflows can happen during model inference.
                pass
            try:
                self._q.put_nowait(indata.copy())
            except queue.Full:
                try:
                    self._q.get_nowait()
                    self._q.put_nowait(indata.copy())
                except queue.Empty:
                    pass

        with sd.InputStream(device=device_idx, channels=channels, samplerate=samplerate, blocksize=blocksize, dtype="float32", callback=callback):
            while not self._stop.is_set():
                try:
                    data = self._q.get(timeout=0.2)
                except queue.Empty:
                    continue
                mono = to_mono_float32(data)
                mono16 = resample_linear(mono, int(samplerate), self.cfg.target_rate)
                self.chunker.accept(mono16)

    def stop(self) -> None:
        self._stop.set()

    def _select_device(self, sd):
        source = self.cfg.source.lower().strip()
        devices = sd.query_devices()
        if source != "auto":
            for idx, dev in enumerate(devices):
                name = str(dev.get("name", ""))
                if source in name.lower() and int(dev.get("max_input_channels", 0)) > 0:
                    sr = int(dev.get("default_samplerate") or 48000)
                    ch = min(2, int(dev.get("max_input_channels") or 1))
                    return idx, sr, ch
            raise RuntimeError(f"No input device matching source={self.cfg.source!r}")

        # Prefer monitor/loopback devices on Linux/PipeWire/PulseAudio if present.
        preferred_patterns = ["monitor", "loopback", "blackhole", "soundflower", "stereo mix", "what u hear"]
        for pat in preferred_patterns:
            for idx, dev in enumerate(devices):
                name = str(dev.get("name", ""))
                if pat in name.lower() and int(dev.get("max_input_channels", 0)) > 0:
                    sr = int(dev.get("default_samplerate") or 48000)
                    ch = min(2, int(dev.get("max_input_channels") or 1))
                    return idx, sr, ch

        default_idx = sd.default.device[0]
        if default_idx is None or default_idx < 0:
            raise RuntimeError("No default input device. On macOS/Linux configure a loopback/monitor input first.")
        dev = devices[default_idx]
        sr = int(dev.get("default_samplerate") or 48000)
        ch = min(2, int(dev.get("max_input_channels") or 1))
        return default_idx, sr, ch


def make_capture(cfg: AudioConfig, on_chunk: Callable[[np.ndarray], None], on_status: Callable[[str], None] | None = None) -> AudioCaptureBase:
    if platform.system().lower() == "windows":
        return WindowsLoopbackCapture(cfg, on_chunk, on_status)
    return SoundDeviceCapture(cfg, on_chunk, on_status)


def list_devices_text() -> str:
    lines: list[str] = []
    if platform.system().lower() == "windows":
        try:
            import pyaudiowpatch as pyaudio
            pa = pyaudio.PyAudio()
            try:
                lines.append("[Windows PyAudioWPatch devices]")
                for i in range(pa.get_device_count()):
                    dev = pa.get_device_info_by_index(i)
                    lines.append(f"{i:>3}: {dev.get('name')} | input={dev.get('maxInputChannels')} output={dev.get('maxOutputChannels')} loopback={dev.get('isLoopbackDevice', False)}")
            finally:
                pa.terminate()
        except Exception as exc:
            lines.append(f"PyAudioWPatch unavailable: {exc}")
    try:
        import sounddevice as sd
        lines.append("\n[sounddevice devices]")
        for i, dev in enumerate(sd.query_devices()):
            lines.append(f"{i:>3}: {dev.get('name')} | input={dev.get('max_input_channels')} output={dev.get('max_output_channels')} sr={dev.get('default_samplerate')}")
    except Exception as exc:
        lines.append(f"sounddevice unavailable: {exc}")
    return "\n".join(lines)
