from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from tarkov_ammo_scanner.api import AmmoRepository, demo_ammo
from tarkov_ammo_scanner.capture import ScreenCaptureService
from tarkov_ammo_scanner.hotkeys import GlobalHotkeyService
from tarkov_ammo_scanner.matcher import is_acceptable_match, match_ammo
from tarkov_ammo_scanner.ocr import OcrService
from tarkov_ammo_scanner.ui.main_window import MainWindow
from tarkov_ammo_scanner.ui.overlay import OverlayWindow


class Bridge(QObject):
    scan_requested = Signal()
    demo_requested = Signal()
    refresh_requested = Signal()
    database_ready = Signal(int, str)
    scan_complete = Signal(object, int, int, float, str)
    scan_failed = Signal(str)


class ScannerApplication:
    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.repository = AmmoRepository()
        self.repository.load()
        self.capture = ScreenCaptureService()
        self.ocr = OcrService()
        self.overlay = OverlayWindow()
        self.bridge = Bridge()
        self.executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="ammo-scanner")

        self.window = MainWindow(
            on_refresh=self.bridge.refresh_requested.emit,
            on_demo=self.bridge.demo_requested.emit,
            on_scan=self.bridge.scan_requested.emit,
        )

        self.bridge.scan_requested.connect(self.scan)
        self.bridge.demo_requested.connect(self.show_demo)
        self.bridge.refresh_requested.connect(self.refresh_database)
        self.bridge.database_ready.connect(self._database_ready)
        self.bridge.scan_complete.connect(self._scan_complete)
        self.bridge.scan_failed.connect(self._scan_failed)

        self.hotkeys = GlobalHotkeyService(
            on_scan=self.bridge.scan_requested.emit,
            on_demo=self.bridge.demo_requested.emit,
        )
        hotkeys_ok = self.hotkeys.start()
        self.window.set_hotkey_status(self.hotkeys.status_text(), ok=hotkeys_ok)
        self.qt_app.aboutToQuit.connect(self.shutdown)

        self._update_ocr_status()
        self.window.show()
        self.refresh_database()

    def refresh_database(self) -> None:
        self.window.set_database_status("База патронов: обновление...", ok=True)

        def worker() -> None:
            items = self.repository.refresh("ru")
            error = self.repository.last_error or ""
            self.bridge.database_ready.emit(len(items), error)

        self.executor.submit(worker)

    def scan(self) -> None:
        if not self.ocr.available:
            self.bridge.scan_failed.emit("Tesseract OCR не найден. Запустите scripts\\setup.ps1")
            return
        if not self.repository.items:
            self.bridge.scan_failed.emit("База патронов ещё не загружена")
            return

        # Do not let a previous result card become part of the next screenshot.
        self.overlay.hide()
        self.window.set_last_scan("Последнее сканирование: обработка снимка...")

        def worker() -> None:
            try:
                image, position = self.capture.capture_title_near_cursor()
                text = self.ocr.recognize(image)
                result = match_ammo(text, self.repository.items)
                acceptable, error_message = is_acceptable_match(result)
                if not acceptable:
                    raise RuntimeError(error_message)

                assert result is not None
                self.bridge.scan_complete.emit(
                    result.ammo,
                    position.x,
                    position.y,
                    result.score,
                    result.recognized_text,
                )
            except Exception as exc:
                self.bridge.scan_failed.emit(str(exc))


        self.executor.submit(worker)

    def show_demo(self) -> None:
        ammo = self.repository.items[0] if self.repository.items else demo_ammo()[0]
        position = self.capture.cursor_position()
        self.overlay.show_ammo(ammo, position.x, position.y)
        self.window.set_last_scan(f"Тестовая карточка: {ammo.short_name}")

    def _database_ready(self, count: int, error: str) -> None:
        if error:
            self.window.set_database_status(
                f"База патронов: {count} записей из кэша/демо. API: {error}",
                ok=False,
            )
        else:
            self.window.set_database_status(f"База патронов: загружено {count}", ok=True)

    def _scan_complete(self, ammo: object, x: int, y: int, score: float, text: str) -> None:
        self.overlay.show_ammo(ammo, x, y)
        recognized = " ".join(text.split())
        self.window.set_last_scan(
            f"Распознано: {ammo.short_name} · уверенность {score:.0f}% · OCR: {recognized[:90]}"
        )

    def _scan_failed(self, message: str) -> None:
        self.window.set_last_scan(f"Ошибка сканирования: {message}", ok=False)

    def _update_ocr_status(self) -> None:
        if not self.ocr.available:
            self.window.set_ocr_status("OCR: Tesseract не найден", ok=False)
            return
        languages = ", ".join(self.ocr.languages()) or "языки не определены"
        has_russian = "rus" in self.ocr.languages()
        self.window.set_ocr_status(
            f"OCR: {self.ocr.executable} · языки: {languages}",
            ok=has_russian,
        )

    def shutdown(self) -> None:
        self.hotkeys.stop()
        self.executor.shutdown(wait=False, cancel_futures=True)


def run() -> int:
    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName("Tarkov Ammo Scanner")
    _application = ScannerApplication(qt_app)
    return qt_app.exec()
