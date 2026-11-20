"""Each character's own strength, whoever controls it (the player, an ally,
an enemy, or the other player online).

Config/stats.json gives every character four numbers, relative to an
average fighter (1.0; Gohan is the reference):

    power    damage of its punches, kicks and techniques
    hp       maximum HP
    defense  how well it takes hits: damage taken is divided by it
    speed    walking and running speed

"power_ups" can say when a character controlled by the game (an ally or an
enemy) transforms: each level with the share of HP left at which it does,
for instance Goku: SSJ at 70% (30% lost), SSJ3 at 50%. A Saiyan without
an entry powers up once, when its difficulty says (difficulty.py).

An enemy's difficulty (Config/enemies.json, difficulty.py) applies on top:
the stats are who the fighter is, the difficulty how hard the AI plays.
A character missing from the file is average.
"""

import json
import os
from dataclasses import dataclass

from utils.config import Config


@dataclass(frozen=True)
class Stats:
    power: float = 1.0
    hp: float = 1.0
    defense: float = 1.0
    speed: float = 1.0


AVERAGE = Stats()

_stats = None
_power_ups = None


def _load():
    global _stats, _power_ups
    if _stats is None:
        path = os.path.join(os.path.dirname(os.path.normpath(Config.CONFIG_DIR)), "stats.json")
        try:
            with open(path) as file:
                data = json.load(file)
        except (OSError, ValueError):
            data = {}
        _stats = {name: Stats(**values) for name, values in data.get("characters", {}).items()}
        _power_ups = {}
        for name, steps in data.get("power_ups", {}).items():
            try:
                # Weakest level (most HP left) first
                _power_ups[name] = tuple(sorted(((str(form), float(share)) for form, share in steps),
                                                key=lambda step: -step[1]))
            except (TypeError, ValueError):
                continue
    return _stats


def character_stats(name):
    return _load().get(name, AVERAGE)


def power_ups(name):
    """((form, share of HP left), ...) when the game transforms this
    character, weakest level first; () when none is set."""
    _load()
    return _power_ups.get(name, ())
