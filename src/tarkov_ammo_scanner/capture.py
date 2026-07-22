from __future__ import annotations

from dataclasses import dataclass

import mss
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
from pynput.mouse import Controller

from tarkov_ammo_scanner.paths import debug_image_file


@dataclass(frozen=True, slots=True)
class CursorPosition:
    x: int
    y: int


class ScreenCaptureService:
    def __init__(self) -> None:
        self._mouse = Controller()

    def cursor_position(self) -> CursorPosition:
        x, y = self._mouse.position
        return CursorPosition(int(x), int(y))

    def capture_title_near_cursor(self) -> tuple[Image.Image, CursorPosition]:
        position = self.cursor_position()
        # The cursor should be on the inspection magnifier or at the beginning
        # of the title. Keep the strip narrow enough to exclude item quantities
        # and neighbouring inventory labels that previously polluted OCR.
        left = max(0, position.x - 30)
        top = max(0, position.y - 34)
        width = 650
        height = 76

        with mss.mss() as screen:
            monitor = {"left": left, "top": top, "width": width, "height": height}
            shot = screen.grab(monitor)
            image = Image.frombytes("RGB", shot.size, shot.rgb)

        image.save(debug_image_file())
        return image, position


def preprocess_for_ocr(image: Image.Image) -> list[Image.Image]:
    gray = ImageOps.grayscale(image)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = ImageEnhance.Contrast(gray).enhance(2.2)
    gray = gray.resize((gray.width * 3, gray.height * 3), Image.Resampling.LANCZOS)
    gray = gray.filter(ImageFilter.SHARPEN)

    # Multiple variants work better across different UI brightness and scaling.
    binary_125 = gray.point(lambda value: 255 if value > 125 else 0)
    binary_150 = gray.point(lambda value: 255 if value > 150 else 0)
    binary_175 = gray.point(lambda value: 255 if value > 175 else 0)
    return [
        gray,
        binary_125,
        binary_150,
        ImageOps.invert(binary_175),
    ]
