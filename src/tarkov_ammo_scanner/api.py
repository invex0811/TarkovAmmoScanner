from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import requests

from tarkov_ammo_scanner.models import Ammo
from tarkov_ammo_scanner.paths import cache_file


class AmmoRepository:
    BASE_URL = "https://json.tarkov.dev"

    def __init__(self, cache_path: Path | None = None) -> None:
        self._cache_path = cache_path or cache_file()
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "TarkovAmmoScanner/0.1.0"})
        self._items: list[Ammo] = []
        self.last_error: str | None = None

    @property
    def items(self) -> tuple[Ammo, ...]:
        return tuple(self._items)

    def load(self) -> list[Ammo]:
        cached = self.load_cache()
        if cached:
            self._items = cached
        return list(self._items)

    def refresh(self, language: str = "ru") -> list[Ammo]:
        try:
            base = self._get_json("/regular/items")
            localized = self._get_json(f"/regular/items_{language}")
            fallback = self._get_json("/regular/items_en") if language != "en" else localized

            translations = localized.get("data", {})
            fallback_translations = fallback.get("data", {})
            raw_items = base.get("data", {}).get("items", {})
            if not isinstance(raw_items, dict):
                raise ValueError("JSON API returned no item dictionary")

            parsed: list[Ammo] = []
            for item_id, raw in raw_items.items():
                ammo = self._parse_item(str(item_id), raw, translations, fallback_translations)
                if ammo is not None:
                    parsed.append(ammo)

            if not parsed:
                raise ValueError("JSON API returned no ammunition")

            parsed.sort(key=lambda ammo: (ammo.caliber.casefold(), ammo.short_name.casefold()))
            self._items = parsed
            self._write_cache(parsed)
            self.last_error = None
            return list(parsed)
        except Exception as exc:  # network/schema errors must not destroy a good cache
            self.last_error = str(exc)
            if not self._items:
                self._items = self.load_cache() or demo_ammo()
            return list(self._items)

    def load_cache(self) -> list[Ammo]:
        try:
            if not self._cache_path.exists():
                return []
            payload = json.loads(self._cache_path.read_text(encoding="utf-8"))
            return [Ammo(**entry) for entry in payload]
        except (OSError, ValueError, TypeError):
            return []

    def _get_json(self, path: str) -> dict[str, Any]:
        response = self._session.get(f"{self.BASE_URL}{path}", timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError(f"Unexpected response from {path}")
        return payload

    @staticmethod
    def _translated(value: Any, primary: dict[str, str], fallback: dict[str, str]) -> str:
        text = "" if value is None else str(value)
        return primary.get(text) or fallback.get(text) or text

    def _parse_item(
        self,
        item_id: str,
        raw: Any,
        translations: dict[str, str],
        fallback: dict[str, str],
    ) -> Ammo | None:
        if not isinstance(raw, dict):
            return None

        types = {str(value).casefold() for value in raw.get("types", []) if value is not None}
        props = raw.get("properties") or {}
        if not isinstance(props, dict):
            return None

        is_ammo = "ammo" in types or "ammunition" in types or props.get("penetrationPower") is not None
        if not is_ammo:
            return None

        name = self._translated(raw.get("name"), translations, fallback)
        short_name = self._translated(raw.get("shortName"), translations, fallback)
        if not short_name:
            short_name = name

        damage = _int(props.get("damage"))
        penetration = _int(props.get("penetrationPower"))
        if damage <= 0 and penetration <= 0:
            return None

        return Ammo(
            id=str(raw.get("id") or item_id),
            name=name,
            short_name=short_name,
            caliber=str(props.get("caliber") or ""),
            damage=damage,
            penetration_power=penetration,
            armor_damage=_int(props.get("armorDamage")),
            fragmentation_chance=_float(props.get("fragmentationChance")),
            initial_speed=_float(props.get("initialSpeed")),
            tracer=bool(props.get("tracer", False)),
            image_url=str(
                raw.get("gridImageLink")
                or raw.get("iconLink")
                or raw.get("image512pxLink")
                or ""
            ),
        )

    def _write_cache(self, ammo: list[Ammo]) -> None:
        self._cache_path.write_text(
            json.dumps([asdict(item) for item in ammo], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def _int(value: Any) -> int:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return 0


def _float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def demo_ammo() -> list[Ammo]:
    return [
        Ammo(
            id="demo-bp-gzh",
            name="7.62x39мм БП гж",
            short_name="БП гж",
            caliber="Caliber762x39",
            damage=58,
            penetration_power=47,
            armor_damage=63,
            fragmentation_chance=0.12,
            initial_speed=730.0,
            tracer=False,
            image_url="",
        )
    ]
