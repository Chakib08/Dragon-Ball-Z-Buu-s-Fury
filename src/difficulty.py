"""How hard each enemy is to beat.

Config/enemies.json gives every difficulty its numbers (all relative to an
ordinary enemy, "normal": 1.0) and every enemy its difficulty:

    hp                maximum HP (times the normal enemy's)
    damage            damage of its punches and kicks (times)
    damage_taken      share of each hit it takes (times; lower is tougher)
    reaction_ms       wait after stepping into reach before its first strike
    attack_cooldown   time between its strikes (times; lower is faster)
    guard_after_hits  quick hits it takes before it guards (and ripostes)
    guard_ms          how long it guards (optional)
    speed             walking speed (times)
    power_up_at       share of HP left at which it powers up (Super Saiyan)
    technique_every_ms  about how often it tries a special technique
    technique_damage  share of a technique's damage it does (the player's
                      techniques do it all: an enemy's would be too strong)
    dodge             chance it sidesteps a blast or beam coming at it
    block_chance      chance it blocks a foe in its face while waiting to
                      strike (then counters as the guard drops)
    tactics           whether it lines up its techniques and, with others
                      on the same foe, attacks from different sides

"ally" is the strength of the support characters fighting on the player's
side.

Change an enemy's difficulty, or a difficulty's numbers, in that file.
"""

import json
import os
from dataclasses import dataclass, field
from typing import List, Tuple

from utils.config import Config

DEFAULT_DIFFICULTY = "normal"
ALLY_DIFFICULTY = "ally"


@dataclass(frozen=True)
class Difficulty:
    name: str
    label: str
    color: Tuple[int, int, int]
    hp: float = 1.0
    damage: float = 1.0
    damage_taken: float = 1.0
    reaction_ms: int = 200
    attack_cooldown: float = 1.0
    guard_after_hits: int = 2
    guard_ms: int = None
    speed: float = 1.0
    power_up_at: float = 0.5
    technique_every_ms: int = 5000
    technique_damage: float = 0.2
    dodge: float = 0.0
    block_chance: float = 0.0
    tactics: bool = False


@dataclass(frozen=True)
class EnemyProfile:
    name: str
    difficulty: Difficulty
    dialog: List[str] = field(default_factory=list)


_data = None


def _load():
    global _data
    if _data is None:
        path = os.path.join(os.path.dirname(os.path.normpath(Config.CONFIG_DIR)), "enemies.json")
        with open(path) as file:
            _data = json.load(file)
    return _data


def difficulty(name):
    settings = dict(_load()["difficulties"][name])
    settings["color"] = tuple(settings.get("color", (255, 255, 255)))
    settings.setdefault("label", name.title())
    return Difficulty(name=name, **settings)


def enemy_profile(character_name):
    """The enemy's difficulty and lines (normal, and no lines, if unlisted)."""
    entry = _load()["enemies"].get(character_name, {})
    return EnemyProfile(
        name=character_name,
        difficulty=difficulty(entry.get("difficulty", DEFAULT_DIFFICULTY)),
        dialog=list(entry.get("dialog", [])),
    )
