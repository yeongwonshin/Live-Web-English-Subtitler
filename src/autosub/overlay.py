from __future__ import annotations

import queue
import sys
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable

from .utils import wrap_caption


@dataclass
class CaptionMessage:
    text: str
    ttl: float


class SubtitleOverlay:
    """Always-on-top subtitle overlay using Tkinter, with a small close button."""

    def __init__(self, width_ratio: float = 0.82, ttl: float = 6.0, on_close: Callable[[], None] | None = None):
        self.ttl = ttl
        self.queue: queue.Queue[CaptionMessage] = queue.Queue()
        self._last_text_time = 0.0
        self._root: tk.Tk | None = None
        self._label: tk.Label | None = None
        self.width_ratio = width_ratio
        self._macos_window_configured = False
        self._on_close = on_close or (lambda: None)

    def show(self, text: str, ttl: float | None = None) -> None:
        text = text.strip()
        if not text:
            return
        self.queue.put(CaptionMessage(text=text, ttl=ttl or self.ttl))

    def run(self) -> None:
        root = tk.Tk()
        self._root = root
        root.title("Live English Subtitles")
        root.configure(bg="#101010")
        root.overrideredirect(True)
        self._apply_always_on_top()
        try:
            root.attributes("-alpha", 0.92)
        except Exception:
            pass

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        width = int(screen_w * self.width_ratio)
        height = 136
        x = int((screen_w - width) / 2)
        y = int(screen_h - height - 86)
        root.geometry(f"{width}x{height}+{x}+{y}")

        outer = tk.Frame(root, bg="#101010", highlightthickness=1, highlightbackground="#303030")
        outer.pack(fill="both", expand=True)

        # A very small control row keeps the overlay frameless but still gives the user a visible close button.
        control = tk.Frame(outer, bg="#101010", height=22)
        control.pack(fill="x", side="top")
        control.pack_propagate(False)

        close_btn = tk.Button(
            control,
            text="×",
            command=self.close,
            font=("Arial", 15, "bold"),
            fg="white",
            bg="#202020",
            activeforeground="white",
            activebackground="#6b1f1f",
            relief="flat",
            bd=0,
            padx=8,
            pady=0,
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=(0, 6), pady=2)

        hint = tk.Label(
            control,
            text=" drag to move · Esc or × to close ",
            font=("Arial", 10),
            fg="#a8a8a8",
            bg="#101010",
        )
        hint.pack(side="left", padx=8)

        label = tk.Label(
            outer,
            text="Waiting for English audio...",
            font=("Arial", 22, "bold"),
            fg="white",
            bg="#101010",
            justify="center",
            wraplength=width - 54,
            padx=24,
            pady=14,
        )
        label.pack(fill="both", expand=True)
        self._label = label

        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda _event: self.close())
        # Dragging works from the text area and the small hint area, but not from the close button.
        for widget in (outer, control, hint, label):
            widget.bind("<Button-1>", self._start_move)
            widget.bind("<B1-Motion>", self._move_window)

        self._poll_queue()
        self._keep_on_top()
        root.mainloop()

    def close(self) -> None:
        try:
            self._on_close()
        except Exception:
            pass
        root = self._root
        if root is not None:
            try:
                root.destroy()
            except Exception:
                pass

    def _apply_always_on_top(self) -> None:
        root = self._root
        if root is None:
            return
        try:
            root.attributes("-topmost", True)
        except Exception:
            pass
        try:
            root.tk.call("wm", "attributes", root._w, "-topmost", "1")
        except Exception:
            pass
        try:
            root.lift()
        except Exception:
            pass
        if sys.platform == "darwin":
            self._apply_macos_floating_level()

    def _apply_macos_floating_level(self) -> None:
        """Make the Tk window a floating macOS window when PyObjC is available.

        This helps the overlay stay above normal app windows and join all Spaces.
        Browser true-fullscreen may still be controlled by macOS; if the overlay is hidden there,
        use the browser window maximized rather than native fullscreen.
        """
        if self._macos_window_configured:
            return
        try:
            from AppKit import (  # type: ignore
                NSApp,
                NSStatusWindowLevel,
                NSWindowCollectionBehaviorCanJoinAllSpaces,
                NSWindowCollectionBehaviorFullScreenAuxiliary,
                NSWindowCollectionBehaviorStationary,
            )

            app = NSApp()
            if app is None:
                return
            for win in app.windows():
                title = str(win.title())
                if "Live English Subtitles" in title or title == "":
                    win.setLevel_(NSStatusWindowLevel)
                    behavior = win.collectionBehavior()
                    behavior |= NSWindowCollectionBehaviorCanJoinAllSpaces
                    behavior |= NSWindowCollectionBehaviorFullScreenAuxiliary
                    behavior |= NSWindowCollectionBehaviorStationary
                    win.setCollectionBehavior_(behavior)
                    self._macos_window_configured = True
        except Exception:
            # The tkinter topmost fallback still works for ordinary windows.
            pass

    def _keep_on_top(self) -> None:
        root = self._root
        if root is None:
            return
        self._apply_always_on_top()
        try:
            root.after(700, self._keep_on_top)
        except Exception:
            pass

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
        try:
            self._root.after(100, self._poll_queue)
        except Exception:
            pass

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
