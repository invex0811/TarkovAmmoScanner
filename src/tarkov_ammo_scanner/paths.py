from __future__ import annotations

import os
from pathlib import Path


def app_data_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        path = Path(root) / "TarkovAmmoScanner"
    else:
        path = Path.home() / ".tarkov-ammo-scanner"
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def local_tessdata_dir() -> Path:
    explicit = os.environ.get("TARKOV_AMMO_TESSDATA")
    if explicit:
        return Path(explicit)
    return project_root() / "local-data" / "tessdata"


def cache_file() -> Path:
    path = app_data_dir() / "cache" / "ammo_ru.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def debug_image_file() -> Path:
    path = app_data_dir() / "debug" / "last_scan.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def diagnostics_dir() -> Path:
    path = app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def scan_log_file() -> Path:
    path = diagnostics_dir() / "scans.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
