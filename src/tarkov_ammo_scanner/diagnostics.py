from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from tarkov_ammo_scanner.matcher import MatchResult, is_acceptable_match
from tarkov_ammo_scanner.paths import debug_image_file, diagnostics_dir, scan_log_file


@dataclass(frozen=True, slots=True)
class ScanLogRecord:
    timestamp: str
    recognized_text: str
    ammo_id: str | None
    ammo_name: str | None
    ammo_short_name: str | None
    ammo_caliber: str | None
    score: float
    margin: float
    has_valid_caliber: bool
    has_designator_match: bool
    tracer_conflict: bool
    caliber_conflict: bool
    designator_conflict: bool
    is_designator_applicable: bool
    accepted: bool
    rejection_reason: str
    debug_image_path: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def log_scan_result(
    result: MatchResult | None,
    raw_ocr_text: str = "",
    log_file: Path | None = None,
) -> ScanLogRecord:
    target_file = log_file or scan_log_file()
    now_iso = datetime.now(timezone.utc).isoformat()
    image_path_str = str(debug_image_file().resolve())

    if result is None:
        record = ScanLogRecord(
            timestamp=now_iso,
            recognized_text=raw_ocr_text,
            ammo_id=None,
            ammo_name=None,
            ammo_short_name=None,
            ammo_caliber=None,
            score=0.0,
            margin=0.0,
            has_valid_caliber=False,
            has_designator_match=False,
            tracer_conflict=False,
            caliber_conflict=False,
            designator_conflict=False,
            is_designator_applicable=True,
            accepted=False,
            rejection_reason="OCR не вернул подходящее название",
            debug_image_path=image_path_str,
        )
    else:
        accepted, rejection_reason = is_acceptable_match(result)
        record = ScanLogRecord(
            timestamp=now_iso,
            recognized_text=result.recognized_text or raw_ocr_text,
            ammo_id=result.ammo.id if result.ammo else None,
            ammo_name=result.ammo.name if result.ammo else None,
            ammo_short_name=result.ammo.short_name if result.ammo else None,
            ammo_caliber=result.ammo.caliber if result.ammo else None,
            score=round(result.score, 2),
            margin=round(result.margin, 2),
            has_valid_caliber=result.has_valid_caliber,
            has_designator_match=result.has_designator_match,
            tracer_conflict=result.tracer_conflict,
            caliber_conflict=result.caliber_conflict,
            designator_conflict=result.designator_conflict,
            is_designator_applicable=result.is_designator_applicable,
            accepted=accepted,
            rejection_reason=rejection_reason,
            debug_image_path=image_path_str,
        )

    target_file.parent.mkdir(parents=True, exist_ok=True)
    with target_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")

    return record


def format_structured_features(result: MatchResult | None) -> str:
    if result is None:
        return "Признаки: нет данных"

    caliber_str = "✓" if result.has_valid_caliber else ("конфликт" if result.caliber_conflict else "✗")

    if result.has_designator_match:
        designator_str = "✓"
    elif result.designator_conflict:
        designator_str = "конфликт"
    elif not result.is_designator_applicable:
        designator_str = "n/a"
    else:
        designator_str = "✗"

    tracer_str = "конфликт" if result.tracer_conflict else "ok"

    return (
        f"Признаки: калибр: {caliber_str} · designator: {designator_str} · "
        f"tracer: {tracer_str} · score: {result.score:.0f}% · margin: {result.margin:.0f}%"
    )




def open_diagnostics_folder() -> None:
    path = diagnostics_dir()
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.resolve())))
