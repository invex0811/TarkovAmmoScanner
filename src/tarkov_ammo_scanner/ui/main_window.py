from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class MainWindow(QMainWindow):
    def __init__(
        self,
        on_refresh: Callable[[], None],
        on_demo: Callable[[], None],
        on_scan: Callable[[], None],
    ) -> None:
        super().__init__()
        self.setWindowTitle("Tarkov Ammo Scanner")
        self.setMinimumSize(520, 335)
        self.resize(590, 360)

        central = QWidget()
        central.setStyleSheet("background: #202020; color: #eeeeee;")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)

        title = QLabel("Tarkov Ammo Scanner")
        title.setStyleSheet("font-size: 24px; font-weight: 700; color: #ffad46;")
        layout.addWidget(title)

        description = QLabel(
            "Наведите курсор на лупу или начало названия патрона в окне осмотра, "
            "затем нажмите Ctrl + Shift + A."
        )
        description.setWordWrap(True)
        description.setStyleSheet("font-size: 13px; color: #c9c9c9;")
        layout.addWidget(description)

        status_frame = QFrame()
        status_frame.setStyleSheet(
            "QFrame { background: #292929; border: 1px solid #3c3c3c; border-radius: 7px; }"
        )
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(14, 12, 14, 12)
        status_layout.setSpacing(8)

        self.database_status = QLabel("База патронов: загрузка...")
        self.ocr_status = QLabel("OCR: проверка...")
        self.last_scan_status = QLabel("Последнее сканирование: ещё не запускалось")
        for label in (self.database_status, self.ocr_status, self.last_scan_status):
            label.setStyleSheet("font-size: 13px; border: none; background: transparent;")
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            status_layout.addWidget(label)
        layout.addWidget(status_frame)

        hotkey = QLabel("Горячие клавиши:  Ctrl+Shift+A — сканировать   ·   Ctrl+Shift+D — тестовая карточка")
        hotkey.setStyleSheet("color: #aebc8c; font-size: 12px;")
        layout.addWidget(hotkey)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        refresh = QPushButton("Обновить базу")
        demo = QPushButton("Показать тест")
        scan = QPushButton("Сканировать сейчас")
        for button in (refresh, demo, scan):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setMinimumHeight(38)
            button.setStyleSheet(
                "QPushButton { background: #333333; border: 1px solid #505050; border-radius: 5px; "
                "padding: 7px 13px; color: #f1f1f1; }"
                "QPushButton:hover { background: #414141; border-color: #ffad46; }"
                "QPushButton:pressed { background: #272727; }"
            )
        refresh.clicked.connect(on_refresh)
        demo.clicked.connect(on_demo)
        scan.clicked.connect(on_scan)
        buttons.addWidget(refresh)
        buttons.addWidget(demo)
        buttons.addWidget(scan)
        layout.addLayout(buttons)
        layout.addStretch(1)

        note = QLabel(
            "Приложение работает только со снимком экрана и не читает память игры. "
            "Для оверлея используйте Borderless или Windowed."
        )
        note.setWordWrap(True)
        note.setStyleSheet("font-size: 11px; color: #858585;")
        layout.addWidget(note)

    def set_database_status(self, text: str, ok: bool = True) -> None:
        self.database_status.setText(text)
        self.database_status.setStyleSheet(
            f"font-size: 13px; border: none; background: transparent; color: {'#7fce75' if ok else '#e18d75'};"
        )

    def set_ocr_status(self, text: str, ok: bool = True) -> None:
        self.ocr_status.setText(text)
        self.ocr_status.setStyleSheet(
            f"font-size: 13px; border: none; background: transparent; color: {'#7fce75' if ok else '#e18d75'};"
        )

    def set_last_scan(self, text: str, ok: bool = True) -> None:
        self.last_scan_status.setText(text)
        self.last_scan_status.setStyleSheet(
            f"font-size: 13px; border: none; background: transparent; color: {'#dedede' if ok else '#e18d75'};"
        )
