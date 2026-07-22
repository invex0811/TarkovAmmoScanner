from __future__ import annotations

import json
from pathlib import Path

from tarkov_ammo_scanner.diagnostics import (
    format_structured_features,
    log_scan_result,
)
from tarkov_ammo_scanner.matcher import MatchResult
from tarkov_ammo_scanner.models import Ammo


def dummy_ammo() -> Ammo:
    return Ammo(
        id="demo-m80",
        name="7.62x51mm M80",
        short_name="M80",
        caliber="Caliber762x51",
        damage=80,
        penetration_power=45,
        armor_damage=60,
        fragmentation_chance=0.17,
        initial_speed=833.0,
        tracer=False,
        image_url="",
    )


def test_log_scan_result_writes_valid_jsonl(tmp_path: Path) -> None:
    log_file = tmp_path / "scans.jsonl"
    match = MatchResult(
        ammo=dummy_ammo(),
        score=99.5,
        runner_up_score=85.0,
        recognized_text="7.62x51MM M80",
        has_valid_caliber=True,
        has_designator_match=True,
        tracer_conflict=False,
    )

    record = log_scan_result(match, log_file=log_file)

    assert record.accepted is True
    assert log_file.exists()

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    payload = json.loads(lines[0])
    assert payload["recognized_text"] == "7.62x51MM M80"
    assert payload["ammo_short_name"] == "M80"
    assert payload["score"] == 99.5
    assert payload["margin"] == 14.5
    assert payload["has_valid_caliber"] is True
    assert payload["has_designator_match"] is True
    assert payload["tracer_conflict"] is False
    assert payload["accepted"] is True
    assert payload["rejection_reason"] == ""
    assert "last_scan.png" in payload["debug_image_path"]


def test_log_scan_result_handles_none_match(tmp_path: Path) -> None:
    log_file = tmp_path / "scans.jsonl"
    record = log_scan_result(None, raw_ocr_text="garbled garbage", log_file=log_file)

    assert record.accepted is False
    assert record.rejection_reason == "OCR не вернул подходящее название"

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    payload = json.loads(lines[0])
    assert payload["accepted"] is False
    assert payload["ammo_id"] is None
    assert payload["recognized_text"] == "garbled garbage"


def test_format_structured_features() -> None:
    match = MatchResult(
        ammo=dummy_ammo(),
        score=66.0,
        runner_up_score=56.0,
        recognized_text=".02X51MM M80",
        has_valid_caliber=True,
        has_designator_match=True,
        tracer_conflict=False,
    )

    text = format_structured_features(match)
    assert "Признаки:" in text
    assert "калибр: ✓" in text
    assert "designator: ✓" in text
    assert "tracer: ok" in text
    assert "score: 66%" in text
    assert "margin: 10%" in text

    assert format_structured_features(None) == "Признаки: нет данных"
