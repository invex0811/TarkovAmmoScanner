from tarkov_ammo_scanner.matcher import match_ammo, normalize
from tarkov_ammo_scanner.models import Ammo


def ammo(name: str, short_name: str, caliber: str = "Caliber762x39") -> Ammo:
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
        tracer=False,
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
