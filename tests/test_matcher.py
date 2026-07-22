from tarkov_ammo_scanner.matcher import match_ammo, normalize
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
