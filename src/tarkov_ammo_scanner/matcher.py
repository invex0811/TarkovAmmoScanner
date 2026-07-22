from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

from tarkov_ammo_scanner.models import Ammo


@dataclass(frozen=True)
class MatchResult:
    ammo: Ammo
    score: float
    runner_up_score: float
    recognized_text: str
    has_valid_caliber: bool
    has_designator_match: bool
    tracer_conflict: bool
    caliber_conflict: bool = False
    designator_conflict: bool = False
    is_designator_applicable: bool = True

    @property
    def margin(self) -> float:
        return self.score - self.runner_up_score



def is_acceptable_match(result: MatchResult | None) -> tuple[bool, str]:
    if result is None:
        return False, "OCR не вернул подходящее название"

    if result.tracer_conflict:
        return False, "Несоответствие маркера трассера"

    if result.caliber_conflict:
        return False, "Несоответствие калибра в распознанном тексте"

    if result.designator_conflict:
        return False, "Несоответствие дезигнатора в распознанном тексте"

    # High confidence general match
    if result.score >= 72.0 and result.margin >= 6.0:
        return True, ""

    # Structured match with valid caliber, recognized designator, and solid margin
    if (
        result.has_valid_caliber
        and result.has_designator_match
        and result.score >= 50.0
        and result.margin >= 6.0
    ):
        return True, ""

    if result.margin < 6.0:
        return (
            False,
            "Неоднозначное распознавание: "
            f"лучший результат {result.ammo.short_name} "
            f"({result.score:.0f}%, отрыв {result.margin:.0f}%). "
            "Наведите курсор ближе к началу названия и повторите.",
        )

    return False, f"Низкая уверенность {result.score:.0f}%: {result.recognized_text!r}"


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

# Common Tesseract substitutions inside ammunition designations. This form is
# used only in addition to the original OCR text.
_OCR_CONFUSABLES = str.maketrans(
    {
        "o": "0",
        "q": "0",
        "u": "0",
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
_M_DESIGNATOR_RE = re.compile(r"m\d{2,3}[a-z0-9]*", re.IGNORECASE)


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
    query_caliber = _query_caliber_signature(query)
    query_designators = _designators(query)
    query_tracer = _mentions_tracer(query)

    candidate_items = list(items)
    if query_caliber:
        same_caliber = [
            ammo
            for ammo in candidate_items
            if _caliber_signature(ammo.caliber, ammo.name) == query_caliber
        ]
        # Apply a hard caliber filter only when the OCR caliber maps to a real
        # caliber present in the database. Garbled values such as 02x51 are
        # ignored instead of filtering every valid candidate out.
        if same_caliber:
            candidate_items = same_caliber

    ranked: list[tuple[float, Ammo]] = []
    for ammo in candidate_items:
        score = _score_ammo(
            query,
            query_tokens,
            query_caliber,
            query_designators,
            query_tracer,
            ammo,
        )
        ranked.append((score, ammo))

    ranked.sort(key=lambda entry: entry[0], reverse=True)
    best_score, best_ammo = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else 0.0

    best_caliber = _caliber_signature(best_ammo.caliber, best_ammo.name)
    best_designators = _designators(f"{best_ammo.short_name} {best_ammo.name}")

    has_valid_caliber = bool(query_caliber and query_caliber == best_caliber)
    has_designator_match = bool(query_designators & best_designators) or (
        _designation_similarity(query_designators, best_designators) >= 65.0
    )
    tracer_conflict = bool(query_tracer and not best_ammo.tracer)

    caliber_conflict = bool(query_caliber and query_caliber != best_caliber)
    designator_conflict = bool(query_designators) and not has_designator_match
    is_designator_applicable = bool(best_designators)

    return MatchResult(
        ammo=best_ammo,
        score=best_score,
        runner_up_score=runner_up,
        recognized_text=text.strip(),
        has_valid_caliber=has_valid_caliber,
        has_designator_match=has_designator_match,
        tracer_conflict=tracer_conflict,
        caliber_conflict=caliber_conflict,
        designator_conflict=designator_conflict,
        is_designator_applicable=is_designator_applicable,
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


def _score_ammo(
    query: str,
    query_tokens: set[str],
    query_caliber: str,
    query_designators: set[str],
    query_tracer: bool,
    ammo: Ammo,
) -> float:
    short = compact(ammo.short_name)
    name = compact(ammo.name)
    caliber = _caliber_signature(ammo.caliber, ammo.name)
    ammo_designators = _designators(f"{ammo.short_name} {ammo.name}")

    short_forms = {short, short.translate(_OCR_CONFUSABLES)} - {""}
    name_forms = {name, name.translate(_OCR_CONFUSABLES)} - {""}

    short_score = _token_similarity(query_tokens, short_forms)
    caliber_score = _caliber_similarity(query_tokens, caliber)
    designation_score = _designation_similarity(query_designators, ammo_designators)

    # Exact structured evidence is more trustworthy than generic fuzzy text.
    exact_caliber = bool(query_caliber and caliber == query_caliber)
    exact_designator = bool(query_designators & ammo_designators)
    exact_short_token = bool(short and short in query_tokens)

    # One- and two-character aliases are extremely unsafe with OCR noise. They
    # may only become plausible when the caliber is also recognized.
    if len(short) < 3:
        if not exact_caliber:
            short_score = min(short_score, 45.0)
        else:
            short_score = min(short_score, 70.0)

    exact_short = len(short) >= 3 and any(
        query_token == short_form
        for query_token in query_tokens
        for short_form in short_forms
    )

    full_score = 0.0
    for form in name_forms:
        if len(form) < 5:
            continue
        full_score = max(full_score, float(fuzz.partial_ratio(compact(query), form)))

    if exact_designator and exact_caliber:
        combined = 98.0
    elif exact_designator:
        combined = 93.0
    elif designation_score >= 82 and exact_caliber:
        combined = designation_score * 0.78 + 20.0
    elif exact_short and exact_caliber:
        combined = 96.0
    elif exact_short:
        combined = 91.0
    elif short_score >= 78 and caliber_score >= 70:
        combined = short_score * 0.72 + caliber_score * 0.28
    elif short_score >= 82 and len(short) >= 4:
        combined = short_score * 0.90 + caliber_score * 0.10
    else:
        combined = max(short_score, min(full_score, 84.0), designation_score)

    if exact_caliber:
        combined += 1.5

    if exact_short_token:
        combined += 2.0

    if query_tracer:
        combined += 2.0 if ammo.tracer else -12.0

    # Generic fuzzy matching is useful as a fallback for long names, but must
    # never recreate a perfect partial-match result on tiny aliases.
    if len(name) >= 8:
        generic = max(
            float(fuzz.WRatio(query, normalize(ammo.name))),
            float(fuzz.token_set_ratio(query, normalize(ammo.name))),
        )
        combined = max(combined, min(generic, 86.0))

    return max(0.0, min(100.0, combined))


def _token_similarity(query_tokens: set[str], candidate_forms: set[str]) -> float:
    best = 0.0
    for query_token in query_tokens:
        for candidate in candidate_forms:
            if not candidate:
                continue
            if query_token == candidate:
                best = max(best, 100.0)
                continue

            if abs(len(query_token) - len(candidate)) <= max(2, len(candidate) // 3):
                best = max(best, float(fuzz.ratio(query_token, candidate)))

            if len(candidate) >= 4 and len(query_token) >= len(candidate):
                best = max(best, min(92.0, float(fuzz.partial_ratio(query_token, candidate))))
    return best


def _designators(text: str) -> set[str]:
    found: set[str] = set()
    for token in _TOKEN_RE.findall(normalize(text)):
        raw = compact(token)
        for form in {raw, raw.translate(_OCR_CONFUSABLES)}:
            found.update(match.group(0) for match in _M_DESIGNATOR_RE.finditer(form))
    return found


def _designation_similarity(query: set[str], candidate: set[str]) -> float:
    if not query or not candidate:
        return 0.0
    if query & candidate:
        return 100.0

    valid_pairs = [
        float(fuzz.ratio(left, right))
        for left in query
        for right in candidate
        if len(left) >= 3 and len(right) >= 3
    ]
    return max(valid_pairs) if valid_pairs else 0.0



def _mentions_tracer(text: str) -> bool:
    normalized = normalize(text)
    return "tracer" in normalized or "трасс" in normalized


def _query_caliber_signature(query: str) -> str:
    norm = normalize(query)
    for form in (norm, norm.translate(_OCR_CONFUSABLES)):
        # Robust caliber recognition accounting for common Tesseract artifacts
        if re.search(
            r"(?<!\d)\.?(?:7[.,]?62|0[.,]?2|0[.,]?6|1[.,]?6|0e|c0c|02|06)\s*x\s*(?:51|i1|il|11|1l|s1|5l|514)(?!\d)",
            form,
        ):
            return "76251"
        if re.search(r"(?<!\d)\.?(?:7[.,]?62|0[.,]?2|0[.,]?6|1[.,]?6)\s*x\s*39(?!\d)", form):
            return "76239"
        if re.search(r"(?<!\d)\.?(?:7[.,]?62|0[.,]?2|0[.,]?6|1[.,]?6)\s*x\s*54(?!\d)", form):
            return "76254"
        if re.search(r"(?<!\d)5[.,]?45\s*x\s*39(?!\d)", form):
            return "54539"
        if re.search(r"(?<!\d)5[.,]?56\s*x\s*45(?!\d)", form):
            return "55645"
        if re.search(r"(?<!\d)5[.,]?7\s*x\s*28(?!\d)", form):
            return "5728"
        if re.search(r"(?<!\d)4[.,]?6\s*x\s*30(?!\d)", form):
            return "4630"
        if re.search(r"(?<!\d)12[.,]?7\s*x\s*55(?!\d)", form):
            return "12755"

        match = re.search(
            r"(?<!\d)(\d)[.,]?(\d{1,2})\s*x\s*(\d{2,3})(?!\d)",
            form,
        )
        if match:
            return "".join(match.groups())

        compact_form = compact(form)
        match = re.search(r"(?<!\d)(\d{3,4})x(\d{2,3})(?!\d)", compact_form)
        if match:
            return "".join(match.groups())
    return ""


def _caliber_signature(caliber: str, name: str) -> str:
    raw = normalize(caliber).replace("caliber", "")
    match = re.search(r"(\d{3,4})x(\d{2,3})", raw)
    if match:
        return "".join(match.groups())

    for form in (normalize(name), normalize(name).translate(_OCR_CONFUSABLES)):
        match = re.search(r"(\d)[.,]?(\d{1,2})\s*x\s*(\d{2,3})", form)
        if match:
            return "".join(match.groups())
    return ""


def _caliber_similarity(query_tokens: set[str], caliber: str) -> float:
    if not caliber:
        return 0.0

    best = 0.0
    for token in query_tokens:
        digits = re.sub(r"[^0-9]", "", token)
        if len(digits) < 4:
            continue
        best = max(best, float(fuzz.partial_ratio(digits, caliber)))
    return best
