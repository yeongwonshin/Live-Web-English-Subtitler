from __future__ import annotations

import queue
import re
import sys
import tkinter as tk
from dataclasses import dataclass
from typing import Callable


@dataclass
class CaptionMessage:
    text: str
    ttl: float


class SubtitleOverlay:
    """Always-on-top, scrollable subtitle overlay using Tkinter.

    Captions are stored as sentence-level history. New sentences are appended at
    the bottom, older sentences move upward, and the user can scroll back to
    review earlier captions.
    """

    def __init__(
        self,
        width_ratio: float = 0.82,
        ttl: float = 6.0,
        on_close: Callable[[], None] | None = None,
        max_sentences: int = 120,
        height: int = 280,
    ):
        self.ttl = ttl
        self.queue: queue.Queue[CaptionMessage] = queue.Queue()
        self.width_ratio = width_ratio
        self.max_sentences = max(10, max_sentences)
        self.height = max(170, height)
        self._root: tk.Tk | None = None
        self._text: tk.Text | None = None
        self._sentences: list[str] = []
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
            root.attributes("-alpha", 0.93)
        except Exception:
            pass

        screen_w = root.winfo_screenwidth()
        screen_h = root.winfo_screenheight()
        width = int(screen_w * self.width_ratio)
        height = min(self.height, max(180, int(screen_h * 0.38)))
        x = int((screen_w - width) / 2)
        y = int(screen_h - height - 74)
        root.geometry(f"{width}x{height}+{x}+{y}")

        outer = tk.Frame(root, bg="#101010", highlightthickness=1, highlightbackground="#303030")
        outer.pack(fill="both", expand=True)

        control = tk.Frame(outer, bg="#101010", height=24)
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
            text=" scroll for previous captions · drag bar to move · Esc or × to close ",
            font=("Arial", 10),
            fg="#a8a8a8",
            bg="#101010",
        )
        hint.pack(side="left", padx=8)

        body = tk.Frame(outer, bg="#101010")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        scrollbar = tk.Scrollbar(body, orient="vertical", bg="#202020", troughcolor="#101010", relief="flat")
        scrollbar.pack(side="right", fill="y")

        text = tk.Text(
            body,
            wrap="word",
            yscrollcommand=scrollbar.set,
            font=("Arial", 19, "bold"),
            fg="white",
            bg="#101010",
            insertbackground="white",
            selectbackground="#3a3a3a",
            relief="flat",
            bd=0,
            padx=14,
            pady=10,
            spacing1=2,
            spacing2=2,
            spacing3=8,
            cursor="arrow",
        )
        text.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=text.yview)
        text.tag_configure("placeholder", foreground="#9a9a9a", justify="center")
        text.tag_configure("caption", foreground="white", justify="left")
        text.tag_configure("latest", foreground="white", justify="left")
        text.insert("1.0", "Waiting for English audio...", "placeholder")
        text.configure(state="disabled")
        self._text = text

        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda _event: self.close())
        for widget in (outer, control, hint):
            widget.bind("<Button-1>", self._start_move)
            widget.bind("<B1-Motion>", self._move_window)

        # Keep text focused for natural scrolling, but do not drag the window from the caption area.
        text.bind("<Button-1>", lambda _event: text.focus_set())

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
        """Make the Tk window a floating macOS window when PyObjC is available."""
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
        messages: list[CaptionMessage] = []
        while True:
            try:
                messages.append(self.queue.get_nowait())
            except queue.Empty:
                break

        if messages:
            auto_scroll = self._is_near_bottom()
            changed = False
            for message in messages:
                changed = self._ingest_caption(message.text) or changed
            if changed:
                self._render_history(auto_scroll=auto_scroll)

        try:
            self._root.after(100, self._poll_queue)
        except Exception:
            pass

    def _ingest_caption(self, text: str) -> bool:
        changed = False
        for sentence in self._split_sentences(text):
            sentence = self._normalize_sentence(sentence)
            if not sentence:
                continue
            if self._is_repeated_sentence(sentence):
                continue
            self._sentences.append(sentence)
            changed = True
        if changed and len(self._sentences) > self.max_sentences:
            self._sentences = self._sentences[-self.max_sentences :]
        return changed

    def _render_history(self, auto_scroll: bool = True) -> None:
        text = self._text
        if text is None:
            return
        text.configure(state="normal")
        text.delete("1.0", tk.END)
        if not self._sentences:
            text.insert("1.0", "Waiting for English audio...", "placeholder")
        else:
            last_idx = len(self._sentences) - 1
            for idx, sentence in enumerate(self._sentences):
                tag = "latest" if idx == last_idx else "caption"
                separator = "\n" if idx == last_idx else "\n\n"
                text.insert(tk.END, sentence + separator, tag)
        text.configure(state="disabled")
        if auto_scroll:
            try:
                text.see(tk.END)
            except Exception:
                pass

    def _is_near_bottom(self) -> bool:
        text = self._text
        if text is None:
            return True
        try:
            _first, last = text.yview()
            return last >= 0.97
        except Exception:
            return True

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split transcription output into display units.

        Whisper live chunks sometimes contain complete sentences and sometimes short
        fragments without punctuation. Complete punctuation-delimited sentences are
        preserved, and a final unpunctuated fragment is still displayed so the overlay
        remains responsive during live speech.
        """
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []
        units = re.findall(r"[^.!?]+[.!?]+(?:[\"')\]]+)?|[^.!?]+$", text)
        return [unit.strip() for unit in units if unit.strip()]

    @staticmethod
    def _normalize_sentence(text: str) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _is_repeated_sentence(self, sentence: str) -> bool:
        current = re.sub(r"\W+", " ", sentence.lower()).strip()
        if not current:
            return True
        for previous in self._sentences[-4:]:
            prev = re.sub(r"\W+", " ", previous.lower()).strip()
            if not prev:
                continue
            if current == prev:
                return True
            if len(current) > 18 and len(prev) > 18 and (current in prev or prev in current):
                return True
        return False

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
