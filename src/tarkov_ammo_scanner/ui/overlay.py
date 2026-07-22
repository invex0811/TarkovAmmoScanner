from __future__ import annotations

from importlib.resources import files

import requests
from PySide6.QtCore import QByteArray, QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QImage, QPixmap
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from tarkov_ammo_scanner.models import Ammo
from tarkov_ammo_scanner.ui.styles import (
    ACCENT,
    IMAGE_BACKGROUND,
    IMAGE_BORDER,
    MUTED,
    OVERLAY_BACKGROUND,
    RATING_COLORS,
    TEXT,
)


class OverlayWindow(QWidget):
    image_loaded = Signal(bytes)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setFixedSize(365, 108)

        root = QFrame(self)
        root.setGeometry(0, 0, self.width(), self.height())
        root.setStyleSheet(
            f"QFrame {{ background: {OVERLAY_BACKGROUND}; border: 1px solid #151515; }}"
        )

        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(8, 7, 10, 7)
        root_layout.setSpacing(9)

        image_frame = QFrame()
        image_frame.setFixedSize(94, 94)
        image_frame.setStyleSheet(
            f"QFrame {{ background: {IMAGE_BACKGROUND}; border: 1px solid {IMAGE_BORDER}; }}"
        )
        image_layout = QVBoxLayout(image_frame)
        image_layout.setContentsMargins(3, 3, 3, 3)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setScaledContents(False)
        image_layout.addWidget(self.image_label)

        self.short_name_badge = QLabel(image_frame)
        self.short_name_badge.setGeometry(40, 1, 50, 20)
        self.short_name_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.short_name_badge.setStyleSheet(
            f"color: {TEXT}; font-size: 13px; font-weight: 700; background: transparent; border: none;"
        )

        right = QVBoxLayout()
        right.setContentsMargins(0, 2, 0, 2)
        right.setSpacing(4)

        self.name_label = QLabel()
        self.name_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.name_label.setStyleSheet(
            f"color: {ACCENT}; font-size: 19px; font-weight: 700; background: transparent; border: none;"
        )
        right.addWidget(self.name_label)

        self.stats_label = QLabel()
        self.stats_label.setStyleSheet(
            f"color: {TEXT}; font-size: 12px; background: transparent; border: none;"
        )
        right.addWidget(self.stats_label)

        ratings_row = QHBoxLayout()
        ratings_row.setSpacing(6)
        ratings_row.setContentsMargins(0, 0, 0, 0)
        self.rating_labels: list[QLabel] = []
        for armor_class in range(1, 7):
            holder = QVBoxLayout()
            holder.setSpacing(1)
            holder.setContentsMargins(0, 0, 0, 0)
            box = QLabel("0")
            box.setFixedSize(23, 22)
            box.setAlignment(Qt.AlignmentFlag.AlignCenter)
            box.setToolTip(f"Класс брони {armor_class}")
            cls = QLabel(str(armor_class))
            cls.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cls.setStyleSheet(
                f"color: {MUTED}; font-size: 9px; background: transparent; border: none;"
            )
            holder.addWidget(box)
            holder.addWidget(cls)
            ratings_row.addLayout(holder)
            self.rating_labels.append(box)
        ratings_row.addStretch(1)
        right.addLayout(ratings_row)

        root_layout.addWidget(image_frame)
        root_layout.addLayout(right, 1)

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        self.image_loaded.connect(self._apply_image_bytes)
        self._show_placeholder()

    def show_ammo(self, ammo: Ammo, x: int, y: int, duration_ms: int = 7000) -> None:
        self.name_label.setText(ammo.short_name or ammo.name)
        self.short_name_badge.setText(ammo.short_name[:7])
        self.stats_label.setText(
            f"Урон {ammo.damage}   ·   Пробитие {ammo.penetration_power}   ·   Броня {ammo.armor_damage}%"
        )

        for label, rating in zip(self.rating_labels, ammo.armor_ratings, strict=True):
            color = RATING_COLORS[rating]
            foreground = "#ffffff" if rating else "#555555"
            label.setText(str(rating))
            label.setStyleSheet(
                f"background: {color}; color: {foreground}; border: none; border-radius: 4px; "
                "font-size: 13px; font-weight: 700;"
            )

        if ammo.image_url:
            self._load_image_async(ammo.image_url)
        else:
            self._show_placeholder()

        self.move(self._bounded_position(QPoint(x + 18, y + 18)))
        self.show()
        self.raise_()
        self._hide_timer.start(duration_ms)

    def _bounded_position(self, desired: QPoint) -> QPoint:
        screen = QGuiApplication.screenAt(desired) or QGuiApplication.primaryScreen()
        if screen is None:
            return desired
        bounds: QRect = screen.availableGeometry()
        x = min(max(desired.x(), bounds.left()), bounds.right() - self.width())
        y = min(max(desired.y(), bounds.top()), bounds.bottom() - self.height())
        return QPoint(x, y)

    def _load_image_async(self, url: str) -> None:
        from threading import Thread

        def worker() -> None:
            try:
                response = requests.get(url, timeout=8, headers={"User-Agent": "TarkovAmmoScanner/0.1.0"})
                response.raise_for_status()
                self.image_loaded.emit(response.content)
            except requests.RequestException:
                self.image_loaded.emit(b"")

        Thread(target=worker, daemon=True).start()

    def _apply_image_bytes(self, content: bytes) -> None:
        if not content:
            self._show_placeholder()
            return
        image = QImage.fromData(QByteArray(content))
        if image.isNull():
            self._show_placeholder()
            return
        pixmap = QPixmap.fromImage(image).scaled(
            84,
            84,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(pixmap)

    def _show_placeholder(self) -> None:
        svg_path = files("tarkov_ammo_scanner").joinpath("assets/ammo-placeholder.svg")
        widget = QSvgWidget(str(svg_path))
        renderer = widget.renderer()
        pixmap = QPixmap(84, 84)
        pixmap.fill(Qt.GlobalColor.transparent)
        from PySide6.QtGui import QPainter

        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        self.image_label.setPixmap(pixmap)
