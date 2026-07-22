from __future__ import annotations

import ctypes
import os
import threading
import traceback
from collections.abc import Callable


class GlobalHotkeyService:
    """Register application-wide hotkeys.

    Windows uses RegisterHotKey so shortcuts work independently of the active
    keyboard layout. Other platforms retain a pynput fallback for development.
    """

    MOD_CONTROL = 0x0002
    MOD_SHIFT = 0x0004
    MOD_NOREPEAT = 0x4000
    WM_HOTKEY = 0x0312
    WM_QUIT = 0x0012

    HOTKEY_SCAN = 1
    HOTKEY_DEMO = 2
    VK_A = 0x41
    VK_D = 0x44

    def __init__(self, on_scan: Callable[[], None], on_demo: Callable[[], None]) -> None:
        self._callbacks = {
            self.HOTKEY_SCAN: on_scan,
            self.HOTKEY_DEMO: on_demo,
        }
        self._thread: threading.Thread | None = None
        self._thread_id: int | None = None
        self._ready = threading.Event()
        self._registered_ids: set[int] = set()
        self._fallback_listener = None
        self.last_error = ""

    def start(self) -> bool:
        if os.name != "nt":
            return self._start_fallback()

        self._ready.clear()
        self._thread = threading.Thread(
            target=self._windows_message_loop,
            name="tarkov-ammo-hotkeys",
            daemon=True,
        )
        self._thread.start()
        self._ready.wait(timeout=3)
        return bool(self._registered_ids)

    def stop(self) -> None:
        if self._fallback_listener is not None:
            self._fallback_listener.stop()
            self._fallback_listener = None

        if os.name == "nt" and self._thread_id is not None:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.PostThreadMessageW(self._thread_id, self.WM_QUIT, 0, 0)

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=2)
        self._thread = None
        self._thread_id = None
        self._registered_ids.clear()

    def status_text(self) -> str:
        labels: list[str] = []
        if self.HOTKEY_SCAN in self._registered_ids:
            labels.append("Ctrl+Shift+A")
        if self.HOTKEY_DEMO in self._registered_ids:
            labels.append("Ctrl+Shift+D")

        if labels:
            text = "Hotkeys active: " + ", ".join(labels)
            if self.last_error:
                text += f". Warning: {self.last_error}"
            return text
        return f"Hotkeys unavailable: {self.last_error or 'registration failed'}"

    def _windows_message_loop(self) -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._thread_id = int(kernel32.GetCurrentThreadId())

        modifiers = self.MOD_CONTROL | self.MOD_SHIFT | self.MOD_NOREPEAT
        definitions = (
            (self.HOTKEY_SCAN, self.VK_A, "Ctrl+Shift+A"),
            (self.HOTKEY_DEMO, self.VK_D, "Ctrl+Shift+D"),
        )
        errors: list[str] = []

        for hotkey_id, virtual_key, label in definitions:
            ctypes.set_last_error(0)
            success = user32.RegisterHotKey(None, hotkey_id, modifiers, virtual_key)
            if success:
                self._registered_ids.add(hotkey_id)
            else:
                error_code = ctypes.get_last_error()
                errors.append(f"{label} (WinError {error_code})")

        self.last_error = "; ".join(errors)
        self._ready.set()

        if not self._registered_ids:
            return

        class Point(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

        class Message(ctypes.Structure):
            _fields_ = [
                ("hwnd", ctypes.c_void_p),
                ("message", ctypes.c_uint),
                ("wParam", ctypes.c_size_t),
                ("lParam", ctypes.c_ssize_t),
                ("time", ctypes.c_uint),
                ("pt", Point),
                ("lPrivate", ctypes.c_uint),
            ]

        message = Message()
        try:
            while True:
                result = user32.GetMessageW(ctypes.byref(message), None, 0, 0)
                if result <= 0:
                    break
                if message.message != self.WM_HOTKEY:
                    continue

                callback = self._callbacks.get(int(message.wParam))
                if callback is None:
                    continue
                try:
                    callback()
                except Exception:  # a hotkey thread must not silently die
                    traceback.print_exc()
        finally:
            for hotkey_id in tuple(self._registered_ids):
                user32.UnregisterHotKey(None, hotkey_id)
            self._registered_ids.clear()

    def _start_fallback(self) -> bool:
        try:
            from pynput import keyboard

            self._fallback_listener = keyboard.GlobalHotKeys(
                {
                    "<ctrl>+<shift>+a": self._callbacks[self.HOTKEY_SCAN],
                    "<ctrl>+<shift>+d": self._callbacks[self.HOTKEY_DEMO],
                }
            )
            self._fallback_listener.start()
            self._registered_ids.update({self.HOTKEY_SCAN, self.HOTKEY_DEMO})
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False
