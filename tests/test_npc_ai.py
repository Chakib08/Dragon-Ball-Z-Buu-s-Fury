"""The NPCs' smarter moves (npc_ai.py) and Goku's power-ups (stats.py)."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from combat import CombatSystem
from effects import Projectile
from npc import HEROES, NPC, SaiyanNPC
from saiyan import Saiyan
from stats import power_ups
from utils.config import Config
from average_stats import use_average_stats


class Clock:
    def __init__(self, test, now=1000):
        self.now = now
        patcher = patch("combat.pygame.time.get_ticks", side_effect=lambda: self.now)
        patcher.start()
        test.addCleanup(patcher.stop)


class SmartNpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        use_average_stats(self)
        self.clock = Clock(self)
        self.player = Saiyan(100, 100, False, "goku")
        self.player.update()
        self.combat = CombatSystem(self.player, (1200, 540))

    def enemy(self, x, y, name="gohan", difficulty="normal"):
        enemy = NPC(x, y, False, name, 0, [], difficulty=difficulty)
        enemy.update()
        return enemy

    def lucky(self, value=0.0):
        """The NPCs' chance rolls come out as value (0: always succeed)."""
        patcher = patch("npc_ai.random.random", return_value=value)
        patcher.start()
        self.addCleanup(patcher.stop)

    # ---- Dodging ---------------------------------------------------------------
    def blast_at(self, enemy):
        """A ki blast from the player's side, flying right at enemy."""
        frame = pygame.Surface((8, 8))
        start = (enemy.rect.centerx - 100, enemy.rect.centery)
        blast = Projectile([frame], [], start, "Right", speed=4, max_range=400, damage=10, on_hit=None)
        blast.team = HEROES
        self.combat.add_effect(blast)
        return blast

    def test_a_smart_npc_sidesteps_a_blast_coming_at_it(self):
        self.lucky(0.0)
        enemy = self.enemy(300, 100)
        self.blast_at(enemy)
        start_y = enemy.position[1]
        self.combat.update([enemy], [])
        self.assertNotEqual(enemy.position[1], start_y)  # across the blast's path
        self.assertTrue(enemy.animation_name.startswith("Run"))

    def test_an_unlucky_or_easy_npc_does_not(self):
        self.lucky(0.99)
        enemy = self.enemy(300, 100)
        self.blast_at(enemy)
        self.assertIsNotNone(self.combat.ai.incoming(enemy))
        self.assertFalse(self.combat.ai.dodge(enemy, []))
        self.assertEqual(self.enemy(300, 100, difficulty="easy").dodge_chance, 0.15)

    def test_its_own_sides_blasts_and_blasts_going_away_are_no_threat(self):
        enemy = self.enemy(300, 100)
        blast = self.blast_at(enemy)
        blast.team = enemy.team
        self.assertIsNone(self.combat.ai.incoming(enemy))
        blast.team = HEROES
        blast.direction = (-1, 0)  # flying away
        self.assertIsNone(self.combat.ai.incoming(enemy))

    # ---- Blocking ----------------------------------------------------------------
    def test_up_close_and_waiting_to_strike_it_blocks_then_counters(self):
        self.lucky(0.0)
        enemy = self.enemy(112, 100)  # within punching reach
        enemy.facing = "Left"
        self.player.facing = "Right"
        self.clock.now = 1000
        self.combat.update([enemy], [])  # just arrived: reaction time first
        self.assertTrue(enemy.blocking)
        self.assertTrue(enemy.riposte_ready)
        # Once the guard drops, the counter comes at once
        hp = self.player.hp
        self.clock.now += enemy.guard_ms + 1
        self.combat.update([enemy], [])
        self.combat.update([enemy], [])
        self.assertLess(self.player.hp, hp)

    def test_it_does_not_block_a_foe_turning_its_back(self):
        self.lucky(0.0)
        enemy = self.enemy(120, 100)
        self.player.facing = "Left"
        self.assertFalse(self.combat.ai.block(enemy, self.player, 1000))

    # ---- Lining up a technique ---------------------------------------------------
    def test_from_a_distance_it_lines_up_with_its_target_to_fire(self):
        enemy = self.enemy(260, 160)  # out of line: 60 px lower
        enemy.ki = enemy.max_ki
        enemy.next_technique_ms = 0
        enemy.combat_engaged = True
        gap = abs(enemy.feet.centery - self.player.feet.centery)
        fired = False
        for _ in range(240):
            self.clock.now += 17
            self.combat.update([enemy], [])
            if enemy.action is not None and enemy.action["name"] == "special":
                fired = True
                break
        self.assertTrue(fired)
        self.assertLess(abs(enemy.feet.centery - self.player.feet.centery), gap)

    def test_it_gives_up_lining_up_after_a_while(self):
        enemy = self.enemy(260, 160)
        enemy.ki = enemy.max_ki
        enemy.next_technique_ms = 0
        ai = self.combat.ai
        self.assertTrue(ai.line_up(enemy, self.player, 1000, []))
        self.assertFalse(ai.line_up(enemy, self.player, 1000 + ai.LINEUP_MS + 1, []))
        self.assertGreater(enemy.next_technique_ms, 1000)

    def test_without_tactics_it_just_comes_at_its_target(self):
        enemy = self.enemy(260, 160, difficulty="easy")
        enemy.ki, enemy.next_technique_ms = enemy.max_ki, 0
        self.assertFalse(self.combat.ai.line_up(enemy, self.player, 1000, []))
        self.assertEqual(self.combat.ai.approach_point(enemy, self.player), self.player.feet.center)

    # ---- Several on one foe ------------------------------------------------------
    def test_several_on_one_foe_come_from_different_sides(self):
        enemies = [self.enemy(300 + 10 * index, 300) for index in range(3)]
        self.combat.update(enemies, [])
        for enemy in enemies:
            enemy.target = self.player
        points = {self.combat.ai.approach_point(enemy, self.player) for enemy in enemies}
        self.assertEqual(len(points), 3)

    def test_it_goes_for_a_beaten_foe_and_allies_protect_the_player(self):
        ally = NPC(100, 140, False, "trunks", 0, [], team=HEROES)
        near, beaten = self.enemy(150, 140), self.enemy(160, 140, name="vegeta")
        for fighter in (ally, near, beaten):
            fighter.update()
        self.combat.update([ally, near, beaten], [])
        beaten.hp = beaten.max_hp * 0.1
        self.assertIs(self.combat.ai.choose_target(ally, self.clock.now), beaten)
        beaten.hp = beaten.max_hp
        near.target = None
        beaten.target = self.player  # beaten one attacks the player
        self.assertIs(self.combat.ai.choose_target(ally, self.clock.now), beaten)


class PowerUpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def setUp(self):
        use_average_stats(self)

    def goku(self, hp_share):
        goku = SaiyanNPC(0, 0, False, "goku", 0, [])
        goku.hp = goku.max_hp * hp_share
        goku.update_ai()
        while goku.update_action():
            pass
        return goku.form

    def test_goku_goes_ssj_after_losing_30_percent_and_ssj3_after_50(self):
        self.assertEqual(power_ups("goku"), (("ssj", 0.7), ("ssj3", 0.5)))
        self.assertEqual(self.goku(0.75), "base")
        self.assertEqual(self.goku(0.7), "ssj")
        self.assertEqual(self.goku(0.5), "ssj3")

    def test_from_ssj_to_ssj3_and_never_back(self):
        goku = SaiyanNPC(0, 0, False, "goku", 0, [])
        goku.hp = goku.max_hp * 0.6
        goku.update_ai()
        while goku.update_action():
            pass
        self.assertEqual(goku.form, "ssj")
        goku.hp = goku.max_hp * 0.4
        goku.update_ai()
        while goku.update_action():
            pass
        self.assertEqual(goku.form, "ssj3")
        goku.update_ai()
        self.assertIsNone(goku.action)
        self.assertEqual(goku.form, "ssj3")

    def test_others_keep_their_difficultys_power_up(self):
        self.assertEqual(power_ups("gohan"), ())
        gohan = SaiyanNPC(0, 0, False, "gohan", 0, [])
        gohan.hp = gohan.max_hp * 0.6
        gohan.update_ai()
        self.assertIsNone(gohan.action)  # normal: at 50%


if __name__ == "__main__":
    unittest.main()
