"""For tests of the game's mechanics (reach, guarding, Super Saiyan
bonuses...): every character with average stats, so the numbers they check
are the rules themselves, not one character's strength (see test_stats.py)."""

from unittest.mock import patch

from stats import AVERAGE


def use_average_stats(test):
    """Characters made during test (a unittest.TestCase) are all average."""
    patcher = patch("character.character_stats", return_value=AVERAGE)
    patcher.start()
    test.addCleanup(patcher.stop)
