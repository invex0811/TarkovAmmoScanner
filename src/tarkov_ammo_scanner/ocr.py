from __future__ import annotations

import ctypes
import os
import shutil
from pathlib import Path

import pytesseract
from PIL import Image

from tarkov_ammo_scanner.capture import preprocess_for_ocr
from tarkov_ammo_scanner.paths import local_tessdata_dir


class OcrUnavailableError(RuntimeError):
    pass


class OcrService:
    def __init__(self) -> None:
        self.executable = self._find_tesseract()
        self.tessdata_dir = self._find_tessdata_dir()

        if self.executable:
            pytesseract.pytesseract.tesseract_cmd = self.executable

        # Tesseract on Windows can treat quotes in --tessdata-dir as literal
        # characters. Set the environment variable as a second, native way to
        # locate the language models and pass a quote-free command-safe path.
        if self.tessdata_dir:
            os.environ["TESSDATA_PREFIX"] = str(self.tessdata_dir.resolve())

    @property
    def available(self) -> bool:
        return bool(self.executable and self.tessdata_dir and self.languages())

    def languages(self) -> list[str]:
        if not self.executable or not self.tessdata_dir:
            return []
        try:
            return sorted(pytesseract.get_languages(config=self._tessdata_config()))
        except (pytesseract.TesseractError, OSError):
            return []

    def recognize(self, image: Image.Image) -> str:
        if not self.executable:
            raise OcrUnavailableError("Tesseract OCR не найден")
        if not self.tessdata_dir:
            raise OcrUnavailableError("Модели Tesseract не найдены. Запустите scripts\\setup.ps1")

        available_languages = set(self.languages())
        if not available_languages:
            raise OcrUnavailableError(
                f"Tesseract не смог загрузить модели из {self.tessdata_dir}. "
                "Повторно запустите scripts\\setup.ps1"
            )

        language = "rus+eng" if "rus" in available_languages and "eng" in available_languages else "eng"
        if "eng" not in available_languages:
            language = next(iter(available_languages))

        texts: list[str] = []
        for variant in preprocess_for_ocr(image):
            for psm in (7, 6, 11):
                text = pytesseract.image_to_string(
                    variant,
                    lang=language,
                    config=f"{self._tessdata_config()} --oem 3 --psm {psm}",
                    timeout=8,
                ).strip()
                if text:
                    texts.append(text)

        if not texts:
            return ""

        # Longer OCR output usually contains the complete inspection title;
        # the fuzzy matcher is robust to surrounding UI text.
        return max(texts, key=lambda text: (len(text), text.count(" ")))

    def _tessdata_config(self) -> str:
        if not self.tessdata_dir:
            return ""
        return f"--tessdata-dir {self._command_safe_path(self.tessdata_dir)}"

    @staticmethod
    def _command_safe_path(path: Path) -> str:
        resolved = path.resolve()

        # pytesseract uses Windows command-line tokenization where quoted
        # --tessdata-dir values may reach Tesseract with the quote characters
        # still attached. A Windows short path avoids both quotes and spaces.
        if os.name == "nt":
            buffer = ctypes.create_unicode_buffer(32768)
            length = ctypes.windll.kernel32.GetShortPathNameW(  # type: ignore[attr-defined]
                str(resolved), buffer, len(buffer)
            )
            if 0 < length < len(buffer):
                return buffer.value.replace("\\", "/")

        return resolved.as_posix()

    def _find_tessdata_dir(self) -> Path | None:
        candidates: list[Path] = [local_tessdata_dir()]
        if self.executable:
            candidates.append(Path(self.executable).parent / "tessdata")

        best: Path | None = None
        best_score = -1
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            score = int((candidate / "eng.traineddata").is_file())
            score += int((candidate / "rus.traineddata").is_file())
            if score > best_score:
                best = candidate
                best_score = score

        return best if best_score > 0 else None

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
