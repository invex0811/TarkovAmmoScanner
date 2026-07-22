from tarkov_ammo_scanner.matcher import MatchResult, is_acceptable_match, match_ammo, normalize
from tarkov_ammo_scanner.models import Ammo
from tarkov_ammo_scanner.ocr import _ocr_text_quality


def ammo(
    name: str,
    short_name: str,
    caliber: str = "Caliber762x39",
    *,
    tracer: bool = False,
) -> Ammo:
    return Ammo(
        id=short_name,
        name=name,
        short_name=short_name,
        caliber=caliber,
        damage=58,
        penetration_power=47,
        armor_damage=63,
        fragmentation_chance=0.12,
        initial_speed=730,
        tracer=tracer,
        image_url="",
    )


def test_normalize_handles_cyrillic_x_and_multiplication_sign() -> None:
    assert normalize("7.62×39 мм БП гж") == "7.62x39 мм бп гж"
    assert normalize("7.62х39 мм БП гж") == "7.62x39 мм бп гж"


def test_matcher_tolerates_ocr_noise() -> None:
    items = [
        ammo("7.62x39мм БП гж", "БП гж"),
        ammo("7.62x39мм ПС гж", "ПС гж"),
    ]
    result = match_ammo("7.62x39mm БП rx", items)
    assert result is not None
    assert result.ammo.short_name == "БП гж"
    assert result.score >= 60


def test_matcher_recovers_m80_from_common_ocr_substitutions() -> None:
    items = [
        ammo("7.62x51mm M80", "M80", "Caliber762x51"),
        ammo("7.62x51mm M62", "M62", "Caliber762x51"),
        ammo("7.62x51mm ME", "ME", "Caliber762x51"),
        ammo("7.62x51mm T", "T", "Caliber762x51"),
    ]
    noisy = "1g (O2XS1MM MEO зо а ts: / - 2 , £3 р | | 58 x x . x |"
    result = match_ammo(noisy, items)
    assert result is not None
    assert result.ammo.short_name == "M80"
    assert result.score >= 90
    assert result.margin >= 8


def test_tiny_alias_cannot_win_from_incidental_substring() -> None:
    items = [
        ammo("7.62x51mm M80", "M80", "Caliber762x51"),
        ammo("7.62x51mm ME", "ME", "Caliber762x51"),
        ammo("7.62x51mm T", "T", "Caliber762x51"),
    ]
    result = match_ammo("random text with me and t around MEO", items)
    assert result is not None
    assert result.ammo.short_name == "M80"
    assert result.score > 80


def test_caliber_and_designator_select_m62_tracer() -> None:
    items = [
        ammo("7.62x51mm M61", "M61", "Caliber762x51"),
        ammo("7.62x51mm M62 Tracer", "M62 Tracer", "Caliber762x51", tracer=True),
        ammo("7.62x51mm M80", "M80", "Caliber762x51"),
        ammo("5.6mm buckshot", "5.6мм", "Caliber20g"),
    ]
    result = match_ammo("40 7.62x51MM M62 Tracer", items)
    assert result is not None
    assert result.ammo.short_name == "M62 Tracer"
    assert result.score >= 98
    assert result.margin >= 10


def test_caliber_filter_blocks_other_caliber_aliases() -> None:
    items = [
        ammo("7.62x51mm M62 Tracer", "M62 Tracer", "Caliber762x51", tracer=True),
        ammo("5.6mm M62", "M62", "Caliber20g"),
    ]
    result = match_ammo("7.62x51MM M62 Tracer", items)
    assert result is not None
    assert result.ammo.caliber == "Caliber762x51"


def test_ocr_quality_prefers_structured_title_over_long_noise() -> None:
    clean = "7.62x51MM M62 Tracer"
    noisy = "40 x x | random inventory text / [] 58 20 36 0 0 0 and more garbage"
    assert _ocr_text_quality(clean) > _ocr_text_quality(noisy)


def test_m62_tracer_recognition_with_ocr_caliber_corruptions() -> None:
    items = [
        ammo("7.62x51mm M61", "M61", "Caliber762x51"),
        ammo("7.62x51mm M62 Tracer", "M62", "Caliber762x51", tracer=True),
        ammo("7.62x51mm M80", "M80", "Caliber762x51"),
        ammo(".300 Blackout M62 Tracer", "M62", "Caliber762x35", tracer=True),
    ]

    for noisy_text in (
        "02X51MM M62 Tracer",
        ".02X51MM M62 Tracer",
        "06X51MM M62 Tracer",
        "7.62x51MM M62 Tracer",
    ):
        result = match_ammo(noisy_text, items)
        assert result is not None
        assert result.ammo.caliber == "Caliber762x51"
        assert result.ammo.short_name == "M62"
        assert result.ammo.tracer is True
        assert result.margin >= 10.0


def test_m80_margin_over_m80a1() -> None:
    items = [
        ammo("7.62x51mm M80", "M80", "Caliber762x51"),
        ammo("7.62x51mm M80A1", "M80A1", "Caliber762x51"),
    ]
    result = match_ammo("7.62x51MM M80", items)
    assert result is not None
    assert result.ammo.short_name == "M80"
    assert result.margin >= 1.0


def test_runtime_acceptance_rules() -> None:
    items = [
        ammo("7.62x51mm M80", "M80", "Caliber762x51"),
        ammo("7.62x51mm M80A1", "M80A1", "Caliber762x51"),
        ammo("7.62x51mm M62 Tracer", "M62", "Caliber762x51", tracer=True),
    ]

    # 1. M80 with OCR caliber corruption (.02X51MM M80) must be accepted
    result_m80 = match_ammo(".02X51MM M80", items)
    assert result_m80 is not None
    assert result_m80.ammo.short_name == "M80"
    assert result_m80.margin >= 8.0
    assert result_m80.has_valid_caliber is True
    assert result_m80.has_designator_match is True
    accepted, _ = is_acceptable_match(result_m80)
    assert accepted is True

    # 2. M80 with fuzzy score around 66 with valid caliber, designator and margin > 8 must be accepted
    struct_m80 = MatchResult(
        ammo=items[0],
        score=66.0,
        recognized_text=".02X51MM M80 noisy OCR",
        runner_up_score=56.0,  # margin 10.0 > 8.0
        has_valid_caliber=True,
        has_designator_match=True,
        tracer_conflict=False,
    )
    accepted, _ = is_acceptable_match(struct_m80)
    assert accepted is True

    # 3. M62 Tracer must be accepted
    result_m62 = match_ammo("02X51MM M62 Tracer", items)
    assert result_m62 is not None
    assert result_m62.ammo.short_name == "M62"
    accepted, _ = is_acceptable_match(result_m62)
    assert accepted is True

    # 4. M80 vs M80A1 must have sufficient margin
    result_m80_vs_a1 = match_ammo("7.62x51MM M80", items)
    assert result_m80_vs_a1 is not None
    assert result_m80_vs_a1.ammo.short_name == "M80"
    assert result_m80_vs_a1.margin >= 10.0

    # 5. Result without valid caliber and small margin must be rejected
    low_confidence_result = MatchResult(
        ammo=items[0],
        score=65.0,
        recognized_text="random text without caliber",
        runner_up_score=62.0,
        has_valid_caliber=False,
        has_designator_match=False,
    )
    accepted, err = is_acceptable_match(low_confidence_result)
    assert accepted is False
    assert "Неоднозначное" in err or "Низкая уверенность" in err



def test_various_calibers_regression() -> None:
    items = [
        # 5.45x39mm
        ammo("5.45x39мм БП гж", "БП гж", "Caliber545x39"),
        ammo("5.45x39мм PP gs", "PP gs", "Caliber545x39"),
        ammo("5.45x39мм 7N39 6g15", "7N39", "Caliber545x39"),
        # 5.56x45mm NATO
        ammo("5.56x45mm M855A1", "M855A1", "Caliber556x45NATO"),
        ammo("5.56x45mm M856A1", "M856A1", "Caliber556x45NATO", tracer=True),
        # 9x19mm
        ammo("9x19mm Pst gzh", "Pst gzh", "Caliber9x19PARA"),
        ammo("9x19mm AP 6.3", "AP 6.3", "Caliber9x19PARA"),
        # .366 TKM
        ammo(".366 TKM AP", "AP", "Caliber366TKM"),
        # 12/70
        ammo("12/70 AP-20 slug", "AP-20", "Caliber12g"),
        # 5.7x28mm
        ammo("5.7x28mm L191", "L191", "Caliber57x28", tracer=True),
        ammo("5.7x28mm SS190", "SS190", "Caliber57x28"),
    ]

    # Test 5.45x39 BP
    r = match_ammo("5.45x39mm BP", items)
    assert r is not None and r.ammo.short_name == "БП гж" and r.ammo.caliber == "Caliber545x39"

    # Test 5.56x45 M855A1
    r = match_ammo("5.56x45mm M855A1", items)
    assert r is not None and r.ammo.short_name == "M855A1" and r.ammo.caliber == "Caliber556x45NATO"

    # Test 9x19 AP 6.3
    r = match_ammo("9x19mm AP 6.3", items)
    assert r is not None and r.ammo.short_name == "AP 6.3" and r.ammo.caliber == "Caliber9x19PARA"

    # Test .366 TKM AP
    r = match_ammo(".366 TKM AP", items)
    assert r is not None and r.ammo.short_name == "AP" and r.ammo.caliber == "Caliber366TKM"

    # Test 12/70 AP-20
    r = match_ammo("12/70 AP-20", items)
    assert r is not None and r.ammo.short_name == "AP-20" and r.ammo.caliber == "Caliber12g"

    # Test 5.7x28mm L191
    r = match_ammo("5.7x28mm L191", items)
    assert r is not None and r.ammo.short_name == "L191" and r.ammo.caliber == "Caliber57x28"
