from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from tarkov_ammo_scanner.models import Ammo


@dataclass(frozen=True, slots=True)
class MatchResult:
    ammo: Ammo
    score: float
    recognized_text: str


_REPLACEMENTS = str.maketrans(
    {
        "×": "x",
        "х": "x",
        "Х": "x",
        "ё": "е",
        "Ё": "Е",
        "—": "-",
        "–": "-",
        "“": '"',
        "”": '"',
    }
)


def normalize(text: str) -> str:
    text = text.translate(_REPLACEMENTS).casefold()
    text = re.sub(r"[^0-9a-zа-я.+\-/ ]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def match_ammo(text: str, items: list[Ammo] | tuple[Ammo, ...]) -> MatchResult | None:
    query = normalize(text)
    if not query or not items:
        return None

    best: MatchResult | None = None
    for ammo in items:
        candidates = {
            normalize(ammo.name),
            normalize(ammo.short_name),
            normalize(f"{ammo.caliber} {ammo.short_name}"),
        }
        score = max(_score(query, candidate) for candidate in candidates if candidate)
        result = MatchResult(ammo=ammo, score=score, recognized_text=text.strip())
        if best is None or result.score > best.score:
            best = result
    return best


def _score(query: str, candidate: str) -> float:
    return max(
        float(fuzz.WRatio(query, candidate)),
        float(fuzz.partial_ratio(query, candidate)),
        float(fuzz.token_set_ratio(query, candidate)),
    )
