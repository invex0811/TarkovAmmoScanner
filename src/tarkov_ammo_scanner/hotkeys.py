from __future__ import annotations

from collections.abc import Callable

from pynput import keyboard


class GlobalHotkeyService:
    def __init__(self, on_scan: Callable[[], None], on_demo: Callable[[], None]) -> None:
        self._listener = keyboard.GlobalHotKeys(
            {
                "<ctrl>+<shift>+a": on_scan,
                "<ctrl>+<shift>+d": on_demo,
            }
        )

    def start(self) -> None:
        self._listener.start()

    def stop(self) -> None:
        self._listener.stop()
