from __future__ import annotations

import ctypes
import os
import re
import shutil
from pathlib import Path

import pytesseract
from PIL import Image

from tarkov_ammo_scanner.capture import preprocess_for_ocr
from tarkov_ammo_scanner.paths import local_tessdata_dir


class OcrUnavailableError(RuntimeError):
    pass


_OCR_CONFUSABLES = str.maketrans(
    {
        "o": "0",
        "q": "0",
        "s": "5",
        "i": "1",
        "l": "1",
        "e": "8",
        "b": "8",
    }
)


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
            # Inspection names are single lines. PSM 7 is the primary mode;
            # PSM 6 remains as a fallback for slightly misaligned captures.
            for psm in (7, 6):
                text = pytesseract.image_to_string(
                    variant,
                    lang=language,
                    config=(
                        f"{self._tessdata_config()} --oem 3 --psm {psm} "
                        "-c preserve_interword_spaces=1"
                    ),
                    timeout=8,
                ).strip()
                if text:
                    texts.append(text)

        if not texts:
            return ""

        # Do not select the longest result: a long inventory row can contain far
        # more OCR garbage than a clean ammo title. Prefer caliber/designation
        # structure and use compactness only as a tie breaker.
        return max(texts, key=lambda text: (_ocr_text_quality(text), -len(text)))

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


def _ocr_text_quality(text: str) -> float:
    from tarkov_ammo_scanner.matcher import _designators, _query_caliber_signature

    normalized = text.casefold().replace("×", "x").replace("х", "x")
    corrected = normalized.translate(_OCR_CONFUSABLES)

    score = 0.0
    caliber_sig = _query_caliber_signature(text)
    if caliber_sig in {"76251", "76239", "76254", "54539", "55645", "5728", "4630", "12755", "12733", "12799", "2375", "939", "919", "918", "921", "114323", "4046"}:
        score += 120.0
    elif any(re.search(r"\b\d[.,]?\d{1,2}\s*x\s*\d{2,3}\b", form) for form in (normalized, corrected)):
        score += 30.0

    if _designators(text) or any(re.search(r"\bm\s*[0-9oqlisb]{2,3}\b", form) for form in (normalized, corrected)):
        score += 75.0

    if "tracer" in normalized or "трасс" in normalized:
        score += 20.0

    alnum_count = sum(character.isalnum() for character in text)
    punctuation_count = sum(
        not character.isalnum() and not character.isspace() for character in text
    )
    score += min(alnum_count, 40) * 0.5
    score -= punctuation_count * 1.5
    score -= max(0, len(text) - 70) * 0.8
    return score
