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


def cache_file() -> Path:
    path = app_data_dir() / "cache" / "ammo_ru.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def debug_image_file() -> Path:
    path = app_data_dir() / "debug" / "last_scan.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path
