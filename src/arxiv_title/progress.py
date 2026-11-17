"""A stderr spinner for slow, silent steps (the markitdown subprocess)."""

from __future__ import annotations

import shutil
import sys
import threading
import time
from typing import TextIO

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
INTERVAL_SECONDS = 0.1


class Spinner:
    """Animate one status line with an elapsed-time counter while work runs.

    The work itself blocks the main thread in `subprocess.run`, so the animation
    lives on a daemon thread. When the stream is not a terminal (pipes, CI logs)
    the label is printed once as a plain line instead, with no control codes.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream if stream is not None else sys.stderr
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._label = ""
        self._started = 0.0

    @property
    def animated(self) -> bool:
        return self.stream.isatty()

    def start(self, label: str) -> None:
        self.stop()
        if not self.animated:
            self.stream.write(f"  {label} ...\n")
            self.stream.flush()
            return
        self._label = label
        self._started = time.monotonic()
        self._stop.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Halt the animation and erase its line. Safe to call when idle."""
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join()
        self._thread = None
        self.stream.write("\r\x1b[K")
        self.stream.flush()

    def _spin(self) -> None:
        tick = 0
        while True:
            self.stream.write("\r\x1b[K" + self._render(tick))
            self.stream.flush()
            tick += 1
            if self._stop.wait(INTERVAL_SECONDS):
                return

    def _render(self, tick: int) -> str:
        frame = FRAMES[tick % len(FRAMES)]
        elapsed = f"{time.monotonic() - self._started:.0f}s"
        # Redrawing with `\r` only works if the line never wraps, so trim the label
        # (paper titles make long filenames) to what the terminal can show.
        room = shutil.get_terminal_size().columns - len(f"  {frame}  {elapsed}") - 1
        label = self._label
        if len(label) > room:
            label = label[: max(room - 1, 0)] + "…"
        return f"  {frame} {label} {elapsed}"
