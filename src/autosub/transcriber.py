from __future__ import annotations

import queue
import re
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass
class AudioSegment:
    audio_16k: np.ndarray
    created_at: float


class WhisperWorker:
    """Background worker for faster-whisper transcription."""

    def __init__(
        self,
        model_name: str = "base.en",
        language: str = "en",
        device: str = "auto",
        compute_type: str = "int8",
        on_text: Callable[[str], None] | None = None,
        on_status: Callable[[str], None] | None = None,
        beam_size: int = 1,
        queue_size: int = 2,
        vad_filter: bool = True,
    ):
        self.model_name = model_name
        self.language = language
        self.device = device
        self.compute_type = compute_type
        self.on_text = on_text or (lambda _text: None)
        self.on_status = on_status or (lambda _text: None)
        self.beam_size = beam_size
        self.vad_filter = vad_filter
        self.queue: queue.Queue[AudioSegment | None] = queue.Queue(maxsize=max(1, queue_size))
        self._last_text = ""
        self._last_text_at = 0.0
        self.thread = threading.Thread(target=self._run, daemon=True)
        self._stop = threading.Event()
        self._loaded = threading.Event()

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            self.queue.put_nowait(None)
        except queue.Full:
            pass

    def submit(self, audio_16k: np.ndarray) -> None:
        if audio_16k.size < 16000 * 0.45:
            return
        # Drop all stale work if the transcriber falls behind. Live subtitles prefer freshness over backlog.
        while self.queue.full():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break
        self.queue.put(AudioSegment(audio_16k.astype(np.float32), time.time()))

    def _run(self) -> None:
        try:
            from faster_whisper import WhisperModel
            model = WhisperModel(
                self.model_name,
                device=self.device,
                compute_type=self.compute_type,
            )
            self._loaded.set()
            self.on_status(f"[Whisper] model loaded: {self.model_name}")
        except Exception as exc:
            self.on_status(f"[Whisper model load failed] {exc}")
            return

        while not self._stop.is_set():
            item = self.queue.get()
            if item is None:
                break
            try:
                segments, info = model.transcribe(
                    item.audio_16k,
                    language=self.language,
                    beam_size=self.beam_size,
                    vad_filter=self.vad_filter,
                    condition_on_previous_text=False,
                    temperature=0.0,
                    no_speech_threshold=0.55,
                )
                text = " ".join(seg.text.strip() for seg in segments).strip()
                text = self._clean_text(text)
                if text and not self._is_duplicate(text):
                    # Actual captions go only to the subtitle sink. They are not status logs.
                    self._last_text = text
                    self._last_text_at = time.time()
                    self.on_text(text)
            except Exception as exc:
                self.on_status(f"[Transcription error] {exc}")

    def _is_duplicate(self, text: str) -> bool:
        now = time.time()
        current = re.sub(r"\W+", " ", text.lower()).strip()
        previous = re.sub(r"\W+", " ", self._last_text.lower()).strip()
        if not current or not previous:
            return False
        if now - self._last_text_at > 8.0:
            return False
        if current == previous:
            return True
        if len(current) > 12 and len(previous) > 12 and (current in previous or previous in current):
            return True
        return False

    @staticmethod
    def _clean_text(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        # Remove common hallucinated filler from very short or silent chunks.
        low = text.lower().strip(" .!?,-")
        bad = {
            "thank you",
            "thanks for watching",
            "you",
            "music",
            "applause",
        }
        if low in bad:
            return ""
        return text
