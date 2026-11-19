"""Each character's own strength, whoever controls it (the player, an ally,
an enemy, or the other player online).

Config/stats.json gives every character four numbers, relative to an
average fighter (1.0; Gohan is the reference):

    power    damage of its punches, kicks and techniques
    hp       maximum HP
    defense  how well it takes hits: damage taken is divided by it
    speed    walking and running speed

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


def _load():
    global _stats
    if _stats is None:
        path = os.path.join(os.path.dirname(os.path.normpath(Config.CONFIG_DIR)), "stats.json")
        try:
            with open(path) as file:
                entries = json.load(file).get("characters", {})
        except (OSError, ValueError):
            entries = {}
        _stats = {name: Stats(**values) for name, values in entries.items()}
    return _stats


def character_stats(name):
    return _load().get(name, AVERAGE)
