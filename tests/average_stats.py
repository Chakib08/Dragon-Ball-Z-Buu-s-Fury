"""For tests of the game's mechanics (reach, guarding, Super Saiyan
bonuses...): every character with average stats, so the numbers they check
are the rules themselves, not one character's strength (see test_stats.py),
and NPCs that never roll a dodge or a block (npc_ai.py: chance decides
those), so what they check happens every time. test_npc_ai.py tests the
rolls themselves."""

from unittest.mock import patch

from stats import AVERAGE


def use_average_stats(test):
    """Characters made during test (a unittest.TestCase) are all average,
    and NPCs fight without lucky dodges or blocks."""
    patcher = patch("character.character_stats", return_value=AVERAGE)
    patcher.start()
    test.addCleanup(patcher.stop)
    steady_npcs(test)


def steady_npcs(test):
    patcher = patch("npc_ai.random.random", return_value=1.0)
    patcher.start()
    test.addCleanup(patcher.stop)


def steady_module_fixtures():
    """setUpModule and tearDownModule for a test file whose NPCs must not
    roll dodges or blocks: setUpModule, tearDownModule = steady_module_fixtures()"""
    patcher = patch("npc_ai.random.random", return_value=1.0)
    return patcher.start, patcher.stop
