from __future__ import annotations

import queue
import threading
import time
import tkinter as tk
from dataclasses import dataclass

from .utils import wrap_caption


@dataclass
class CaptionMessage:
    text: str
    ttl: float


class SubtitleOverlay:
    """Always-on-top subtitle overlay using Tkinter."""

    def __init__(self, width_ratio: float = 0.82, ttl: float = 6.0):
        self.ttl = ttl
        self.queue: queue.Queue[CaptionMessage] = queue.Queue()
        self._last_text_time = 0.0
        self._root: tk.Tk | None = None
        self._label: tk.Label | None = None
        self.width_ratio = width_ratio

    def show(self, text: str, ttl: float | None = None) -> None:
        text = text.strip()
        if not text:
            return
        self.queue.put(CaptionMessage(text=text, ttl=ttl or self.ttl))

    def run(self) -> None:
        root = tk.Tk()
        self._root = root
        root.title("Live English Subtitles")
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.88)
        root.configure(bg="#101010")
        root.overrideredirect(True)

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        width = int(screen_w * self.width_ratio)
        height = 112
        x = int((screen_w - width) / 2)
        y = int(screen_h - height - 86)
        root.geometry(f"{width}x{height}+{x}+{y}")

        label = tk.Label(
            root,
            text="Waiting for English audio...",
            font=("Arial", 22, "bold"),
            fg="white",
            bg="#101010",
            justify="center",
            wraplength=width - 40,
            padx=20,
            pady=18,
        )
        label.pack(fill="both", expand=True)
        self._label = label

        root.bind("<Escape>", lambda _event: root.destroy())
        root.bind("<Button-1>", self._start_move)
        root.bind("<B1-Motion>", self._move_window)

        self._poll_queue()
        root.mainloop()

    def _poll_queue(self) -> None:
        assert self._root is not None
        assert self._label is not None
        now = time.time()
        newest: CaptionMessage | None = None
        while True:
            try:
                newest = self.queue.get_nowait()
            except queue.Empty:
                break
        if newest is not None:
            self._label.configure(text=wrap_caption(newest.text))
            self._last_text_time = now + newest.ttl
        elif self._last_text_time and now > self._last_text_time:
            self._label.configure(text="")
            self._last_text_time = 0.0
        self._root.after(100, self._poll_queue)

    def _start_move(self, event) -> None:
        root = self._root
        if root is None:
            return
        root._drag_x = event.x
        root._drag_y = event.y

    def _move_window(self, event) -> None:
        root = self._root
        if root is None:
            return
        x = root.winfo_pointerx() - getattr(root, "_drag_x", 0)
        y = root.winfo_pointery() - getattr(root, "_drag_y", 0)
        root.geometry(f"+{x}+{y}")
