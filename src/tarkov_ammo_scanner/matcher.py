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
    runner_up_score: float = 0.0

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score


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

# Common Tesseract substitutions inside ammunition designations.  This is used
# only as an additional comparison form; the original normalized text remains
# available, so ordinary words are not permanently rewritten as digits.
_OCR_CONFUSABLES = str.maketrans(
    {
        "o": "0",
        "q": "0",
        "s": "5",
        "i": "1",
        "l": "1",
        "e": "8",
        "b": "8",
        "g": "6",
        "z": "2",
    }
)

_TOKEN_RE = re.compile(r"[0-9a-zа-я.+\-/]{1,}", re.IGNORECASE)


def normalize(text: str) -> str:
    text = text.translate(_REPLACEMENTS).casefold()
    text = re.sub(r"[^0-9a-zа-я.+\-/ ]+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def compact(text: str) -> str:
    return re.sub(r"[^0-9a-zа-я]+", "", normalize(text), flags=re.IGNORECASE)


def match_ammo(text: str, items: list[Ammo] | tuple[Ammo, ...]) -> MatchResult | None:
    query = normalize(text)
    if not query or not items:
        return None

    query_tokens = _query_tokens(query)
    ranked: list[tuple[float, Ammo]] = []

    for ammo in items:
        score = _score_ammo(query, query_tokens, ammo)
        ranked.append((score, ammo))

    ranked.sort(key=lambda entry: entry[0], reverse=True)
    best_score, best_ammo = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0
    return MatchResult(
        ammo=best_ammo,
        score=best_score,
        runner_up_score=runner_up,
        recognized_text=text.strip(),
    )


def _query_tokens(query: str) -> set[str]:
    tokens: set[str] = set()
    for token in _TOKEN_RE.findall(query):
        raw = compact(token)
        if not raw:
            continue
        tokens.add(raw)
        tokens.add(raw.translate(_OCR_CONFUSABLES))

    whole = compact(query)
    if whole:
        tokens.add(whole)
        tokens.add(whole.translate(_OCR_CONFUSABLES))
    return tokens


def _score_ammo(query: str, query_tokens: set[str], ammo: Ammo) -> float:
    short = compact(ammo.short_name)
    name = compact(ammo.name)
    caliber = _caliber_signature(ammo.caliber, ammo.name)

    short_forms = {short, short.translate(_OCR_CONFUSABLES)} - {""}
    name_forms = {name, name.translate(_OCR_CONFUSABLES)} - {""}

    short_score = _token_similarity(query_tokens, short_forms)
    caliber_score = _caliber_similarity(query_tokens, caliber)

    # One- and two-character aliases are extremely unsafe with OCR noise. They
    # may only become plausible when the caliber is also recognized.
    if len(short) < 3:
        if caliber_score < 82:
            short_score = min(short_score, 52.0)
        else:
            short_score = min(short_score, 78.0)

    exact_short = len(short) >= 3 and any(
        query_token == short_form
        for query_token in query_tokens
        for short_form in short_forms
    )
    if exact_short:
        return min(100.0, 96.0 + caliber_score * 0.04)

    full_score = 0.0
    for form in name_forms:
        if len(form) < 5:
            continue
        full_score = max(full_score, float(fuzz.partial_ratio(compact(query), form)))

    if short_score >= 78 and caliber_score >= 70:
        combined = short_score * 0.72 + caliber_score * 0.28
    elif short_score >= 82 and len(short) >= 4:
        combined = short_score * 0.90 + caliber_score * 0.10
    else:
        combined = max(short_score, min(full_score, 84.0))

    # Generic fuzzy matching is useful as a fallback for long names, but must
    # never recreate the old 100% partial-match failure on tiny aliases.
    if len(name) >= 8:
        generic = max(
            float(fuzz.WRatio(query, normalize(ammo.name))),
            float(fuzz.token_set_ratio(query, normalize(ammo.name))),
        )
        combined = max(combined, min(generic, 86.0))

    return min(100.0, combined)


def _token_similarity(query_tokens: set[str], candidate_forms: set[str]) -> float:
    best = 0.0
    for query_token in query_tokens:
        for candidate in candidate_forms:
            if not candidate:
                continue
            if query_token == candidate:
                best = max(best, 100.0)
                continue

            # Compare similarly-sized tokens. This prevents a two-character
            # candidate from matching perfectly inside a long noisy OCR line.
            if abs(len(query_token) - len(candidate)) <= max(2, len(candidate) // 3):
                best = max(best, float(fuzz.ratio(query_token, candidate)))

            if len(candidate) >= 4 and len(query_token) >= len(candidate):
                best = max(best, min(92.0, float(fuzz.partial_ratio(query_token, candidate))))
    return best


def _caliber_signature(caliber: str, name: str) -> str:
    raw = compact(caliber).replace("caliber", "")
    match = re.search(r"\d{3,6}", raw)
    if match:
        digits = match.group(0)
        if len(digits) >= 4:
            return digits

    name_match = re.search(r"(\d)[.,]?(\d{1,2})x(\d{2})", normalize(name))
    if name_match:
        return "".join(name_match.groups())
    return ""


def _caliber_similarity(query_tokens: set[str], caliber: str) -> float:
    if not caliber:
        return 0.0

    forms = {caliber, caliber.translate(_OCR_CONFUSABLES)}
    best = 0.0
    for token in query_tokens:
        digits = re.sub(r"[^0-9]", "", token)
        if len(digits) < 4:
            continue
        for form in forms:
            best = max(best, float(fuzz.partial_ratio(digits, form)))
    return best
