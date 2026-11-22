"""Each character's own stats (Config/stats.json), in every role."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import CombatSystem
from npc import HEROES, NPC, SaiyanNPC
from saiyan import Saiyan
from stats import AVERAGE, character_stats
from utils.config import Config

from average_stats import steady_module_fixtures

# Repeatable NPCs: no lucky dodges or blocks (see average_stats.py)
setUpModule, tearDownModule = steady_module_fixtures()


ROSTER = ("goku", "vegeta", "gohan", "trunks", "broly")


class StatsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        self.now = 10_000
        patcher = patch("pygame.time.get_ticks", side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_every_character_has_stats_and_gohan_is_the_reference(self):
        for name in ROSTER:
            with self.subTest(character=name):
                stats = character_stats(name)
                for value in (stats.power, stats.hp, stats.defense, stats.speed):
                    self.assertTrue(0.5 <= value <= 2.0)
        self.assertEqual(character_stats("gohan"), AVERAGE)
        self.assertEqual(character_stats("nobody"), AVERAGE)

    def test_goku_is_stronger_than_trunks_who_is_faster(self):
        goku, trunks = character_stats("goku"), character_stats("trunks")
        self.assertGreater(goku.power, trunks.power)
        self.assertGreater(goku.hp, trunks.hp)
        self.assertGreater(trunks.speed, goku.speed)

    def test_the_ranking(self):
        power = {name: character_stats(name).power for name in ROSTER}
        self.assertEqual(sorted(power, key=power.get, reverse=True),
                         ["broly", "goku", "vegeta", "trunks", "gohan"])

    def test_trunks_in_armor_is_stronger_than_future_trunks(self):
        armor, future = character_stats("trunks"), character_stats("trunks_future")
        for stat in ("power", "hp", "defense"):
            self.assertGreater(getattr(armor, stat), getattr(future, stat), stat)
        self.assertGreaterEqual(armor.speed, future.speed)

    def test_the_players_character_has_its_own_hp_and_speed(self):
        goku, trunks = Saiyan(0, 0, False, "goku"), Saiyan(0, 0, False, "trunks")
        self.assertEqual(goku.max_hp, round(Saiyan.MAX_HP * 1.1))
        self.assertEqual(goku.hp, goku.max_hp)
        self.assertGreater(goku.max_hp, trunks.max_hp)
        for fighter in (goku, trunks):
            start = fighter.position[0]
            fighter.move("Walk Right", 4)
            fighter.walked = fighter.position[0] - start
        self.assertGreater(trunks.walked, goku.walked)

    def punch(self, attacker_name, defender_name="gohan"):
        """Damage one punch of the player's character does to an enemy."""
        player = Saiyan(100, 100, False, attacker_name)
        player.update()
        player.facing = "Right"
        enemy = NPC(0, 0, False, defender_name, 0, [], difficulty="normal")
        enemy.position = [player.feet.centerx + 15 - enemy.rect.width / 2,
                          player.rect.bottom - enemy.rect.height]
        enemy.update()
        combat = CombatSystem(player, (1200, 540))
        combat.update([enemy], [], player_attacking=True)
        return enemy.max_hp - enemy.hp

    def test_a_stronger_character_hits_harder(self):
        self.assertGreater(self.punch("goku"), self.punch("trunks"))
        self.assertAlmostEqual(self.punch("goku") / self.punch("gohan"), 1.15)

    def test_a_tougher_character_takes_less(self):
        self.assertLess(self.punch("gohan", "broly"), self.punch("gohan", "gohan"))
        self.assertAlmostEqual(self.punch("gohan", "gohan") / self.punch("gohan", "broly"), 1.15)

    def test_techniques_scale_with_power_too(self):
        damage = {}
        for name in ("goku", "trunks"):
            player = Saiyan(0, 0, False, name)
            combat = CombatSystem(player, (1200, 540))
            blast = next(t for t in player.techniques if t.kind == "projectile")
            damage[name] = combat._release_by(player, blast, "Right").damage / blast.damage
        self.assertAlmostEqual(damage["goku"], 1.15)
        self.assertAlmostEqual(damage["trunks"], 1.12)

    def test_an_enemys_difficulty_comes_on_top_of_its_stats(self):
        broly = SaiyanNPC(0, 0, False, "broly", 0, [], difficulty="hard")
        self.assertEqual(broly.difficulty.name, "hard")
        self.assertEqual(broly.max_hp, round(NPC.MAX_HP * 1.3 * 1.8))
        self.assertAlmostEqual(broly.damage_taken, NPC.DAMAGE_TAKEN * 0.6 / 1.15)
        self.assertAlmostEqual(broly.walk_speed, NPC.WALK_SPEED * 0.9 * 1.25)

    def test_allies_keep_their_characters_strength(self):
        goku = SaiyanNPC(0, 0, False, "goku", 0, [], team=HEROES)
        trunks = SaiyanNPC(0, 0, False, "trunks", 0, [], team=HEROES)
        self.assertGreater(goku.max_hp, trunks.max_hp)
        self.assertGreater(goku.power, trunks.power)
        self.assertGreater(trunks.walk_speed, goku.walk_speed)

    def test_goku_usually_beats_trunks_in_a_duel(self):
        """Same AI and difficulty on both sides: the stats decide."""
        import random
        wins = 0
        for seed in range(4):
            random.seed(seed)
            player = Saiyan(-500, -500, False, "gohan")
            player.update()
            combat = CombatSystem(player, (1200, 540))
            goku = SaiyanNPC(0, 0, False, "goku", 0, [], team=HEROES)
            trunks = SaiyanNPC(0, 0, False, "trunks", 0, [], difficulty="normal")
            goku.position, trunks.position = ([100, 100], [130, 100]) if seed % 2 else ([130, 100], [100, 100])
            for fighter in (goku, trunks):
                fighter.update()
                fighter.save_location()
            for _ in range(60 * 400):
                if goku.hp <= 0 or trunks.hp <= 0:
                    break
                self.now += 17
                combat.update([goku, trunks], [])
            wins += trunks.hp <= 0 < goku.hp
        self.assertGreaterEqual(wins, 3)


if __name__ == "__main__":
    unittest.main()
