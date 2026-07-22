from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytesseract
from PIL import Image

from tarkov_ammo_scanner.capture import preprocess_for_ocr


class OcrUnavailableError(RuntimeError):
    pass


class OcrService:
    def __init__(self) -> None:
        self.executable = self._find_tesseract()
        if self.executable:
            pytesseract.pytesseract.tesseract_cmd = self.executable

    @property
    def available(self) -> bool:
        return bool(self.executable)

    def languages(self) -> list[str]:
        if not self.available:
            return []
        try:
            return sorted(pytesseract.get_languages(config=""))
        except pytesseract.TesseractError:
            return []

    def recognize(self, image: Image.Image) -> str:
        if not self.available:
            raise OcrUnavailableError("Tesseract OCR не найден")

        available_languages = set(self.languages())
        language = "rus+eng" if "rus" in available_languages and "eng" in available_languages else "eng"
        if "eng" not in available_languages and available_languages:
            language = next(iter(available_languages))

        texts: list[str] = []
        for variant in preprocess_for_ocr(image):
            for psm in (7, 6, 11):
                text = pytesseract.image_to_string(
                    variant,
                    lang=language,
                    config=f"--oem 3 --psm {psm}",
                    timeout=8,
                ).strip()
                if text:
                    texts.append(text)

        if not texts:
            return ""
        # Longer OCR output usually contains the complete inspection title;
        # the fuzzy matcher is robust to surrounding UI text.
        return max(texts, key=lambda text: (len(text), text.count(" ")))

    @staticmethod
    def _find_tesseract() -> str | None:
        explicit = os.environ.get("TESSERACT_CMD")
        candidates = [
            explicit,
            shutil.which("tesseract"),
            str(Path(os.environ.get("PROGRAMFILES", "")) / "Tesseract-OCR" / "tesseract.exe"),
            str(Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Tesseract-OCR" / "tesseract.exe"),
            str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Tesseract-OCR" / "tesseract.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return str(Path(candidate))
        return None
