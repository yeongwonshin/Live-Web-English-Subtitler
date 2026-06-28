from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def rms_float32(x: np.ndarray) -> float:
    """Return RMS amplitude for float32 audio in [-1, 1]."""
    if x.size == 0:
        return 0.0
    x = np.asarray(x, dtype=np.float32)
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


def to_mono_float32(audio: np.ndarray) -> np.ndarray:
    """Convert int/float mono or multi-channel audio to mono float32 [-1, 1]."""
    arr = np.asarray(audio)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    if arr.dtype == np.int16:
        arr = arr.astype(np.float32) / 32768.0
    elif arr.dtype == np.int32:
        arr = arr.astype(np.float32) / 2147483648.0
    elif arr.dtype == np.uint8:
        arr = (arr.astype(np.float32) - 128.0) / 128.0
    else:
        arr = arr.astype(np.float32)
        # Some APIs return float audio outside [-1, 1] if badly configured.
        mx = float(np.max(np.abs(arr))) if arr.size else 0.0
        if mx > 4.0:
            arr = arr / mx
    return np.clip(arr, -1.0, 1.0).astype(np.float32, copy=False)


def resample_linear(audio: np.ndarray, src_rate: int, dst_rate: int) -> np.ndarray:
    """Small dependency-free mono resampler, good enough for speech transcription."""
    audio = np.asarray(audio, dtype=np.float32)
    if src_rate == dst_rate or audio.size == 0:
        return audio
    duration = audio.size / float(src_rate)
    out_len = max(1, int(round(duration * dst_rate)))
    old_x = np.linspace(0.0, duration, num=audio.size, endpoint=False)
    new_x = np.linspace(0.0, duration, num=out_len, endpoint=False)
    return np.interp(new_x, old_x, audio).astype(np.float32)


def wrap_caption(text: str, width: int = 78, max_lines: int = 2) -> str:
    """Simple word wrapping for overlay captions."""
    words = text.strip().split()
    if not words:
        return ""
    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        extra = len(word) + (1 if current else 0)
        if current and current_len + extra > width:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += extra
    if current:
        lines.append(" ".join(current))
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    return "\n".join(lines)
