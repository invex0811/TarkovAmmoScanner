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
        # The cursor should be on the inspection magnifier or near the beginning
        # of the title. The strip is wide enough for long translated ammo names
        # while remaining short enough to avoid most inventory rows.
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
    # The Tarkov title is normally either at the top of this capture or close to
    # its vertical middle, depending on whether the cursor is on the magnifier
    # or directly on the text. Process narrow title crops before full width so
    # Tesseract is not distracted by item icons and quantities on the right.
    width, height = image.size
    top_band = image.crop((0, 0, width, min(height, 34)))

    # Narrow crop isolating the title text from right-side status indicators
    narrow_top_band = image.crop((0, 0, min(width, 360), min(height, 34)))

    middle_top = max(0, height // 2 - 18)
    middle_bottom = min(height, middle_top + 36)
    middle_band = image.crop((0, middle_top, width, middle_bottom))

    variants: list[Image.Image] = []
    for source, thresholds in (
        (narrow_top_band, (125, 155)),
        (top_band, (125, 155)),
        (middle_band, (135,)),
        (image, (150,)),
    ):
        gray = ImageOps.grayscale(source)
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = ImageEnhance.Contrast(gray).enhance(2.3)
        gray = gray.resize((gray.width * 4, gray.height * 4), Image.Resampling.LANCZOS)
        gray = gray.filter(ImageFilter.SHARPEN)
        variants.append(gray)
        for threshold in thresholds:
            variants.append(gray.point(lambda value, limit=threshold: 255 if value > limit else 0))

    return variants
