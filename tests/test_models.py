from tarkov_ammo_scanner.models import armor_effectiveness


def test_bp_like_penetration_matches_compact_scale() -> None:
    assert tuple(armor_effectiveness(47, armor_class) for armor_class in range(1, 7)) == (
        5,
        5,
        5,
        5,
        4,
        0,
    )


def test_rating_is_bounded() -> None:
    for penetration in range(0, 80):
        for armor_class in range(1, 7):
            assert 0 <= armor_effectiveness(penetration, armor_class) <= 5
