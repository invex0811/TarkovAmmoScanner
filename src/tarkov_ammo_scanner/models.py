from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Ammo:
    id: str
    name: str
    short_name: str
    caliber: str
    damage: int
    penetration_power: int
    armor_damage: int
    fragmentation_chance: float
    initial_speed: float
    tracer: bool
    image_url: str

    @property
    def armor_ratings(self) -> tuple[int, int, int, int, int, int]:
        return tuple(armor_effectiveness(self.penetration_power, armor_class) for armor_class in range(1, 7))


def armor_effectiveness(penetration_power: int, armor_class: int) -> int:
    """Return a compact 0-5 heuristic for a full-durability armor class.

    This intentionally produces a glanceable overlay value rather than pretending
    to simulate a particular armor material, durability, or hit history.
    """
    margin = penetration_power - armor_class * 10
    if margin >= 5:
        return 5
    if margin >= -5:
        return 4
    if margin >= -8:
        return 3
    if margin >= -10:
        return 2
    if margin >= -12:
        return 1
    return 0
