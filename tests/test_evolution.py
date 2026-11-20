"""Becoming another character: the Potara fusion of Goku and Vegeta into
Vegito, Cell absorbing the androids (evolution.py)."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import evolution
from combat import CombatSystem
from npc import NPC, SaiyanNPC
from saiyan import Saiyan
from utils.config import Config
from average_stats import use_average_stats


class Clock:
    def __init__(self, test, now=1000):
        self.now = now
        patcher = patch("combat.pygame.time.get_ticks", side_effect=lambda: self.now)
        patcher.start()
        test.addCleanup(patcher.stop)


def technique(fighter, technique_id):
    return next(t for t in fighter.techniques if t.id == technique_id)


class EvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        use_average_stats(self)
        self.clock = Clock(self)

    def fight(self, name):
        player = Saiyan(200, 200, False, name)
        player.update()
        combat = CombatSystem(player, (1200, 540))
        return player, combat

    def run_frames(self, player, combat, frames=200, npcs=()):
        for _ in range(frames):
            self.clock.now += 17
            player.update_action()
            combat.update(list(npcs), [])

    def use(self, player, combat, technique_id):
        combat.selected_technique = [t.id for t in player.techniques].index(technique_id)
        return combat.start_special()

    def test_goku_and_vegeta_fuse_into_vegito(self):
        for name in ("goku", "vegeta"):
            with self.subTest(character=name):
                player, combat = self.fight(name)
                player.hp = player.max_hp * 0.5
                ground = player.rect.midbottom
                self.assertTrue(self.use(player, combat, "potara"))
                self.assertEqual(player.action["name"], "evolve")
                self.assertIsInstance(combat.effects[-1], evolution.Evolution)
                # Untouchable while fusing
                self.assertEqual(player.take_damage(50), 0)
                self.run_frames(player, combat)
                self.assertEqual(player.character_name, "vegito")
                self.assertIsNone(player.action)
                self.assertEqual(player.rect.midbottom, ground)  # where it stood
                self.assertAlmostEqual(player.hp / player.max_hp, 0.5)
                self.assertIn("Final Kamehameha", [t.name for t in player.techniques])
                self.assertEqual(combat.selected_technique, 0)
                self.assertEqual(combat.effects, [])
                # Vegito can still go Super Saiyan
                self.assertEqual(player.super_levels, ["ssj"])

    def test_it_costs_ki(self):
        player, combat = self.fight("goku")
        player.ki = 10
        self.assertFalse(self.use(player, combat, "potara"))
        self.assertEqual(player.character_name, "goku")

    def test_cell_absorbs_android_17_then_18_to_become_perfect(self):
        player, combat = self.fight("cell_imperfect")
        self.assertTrue(self.use(player, combat, "absorb_17"))
        self.run_frames(player, combat)
        self.assertEqual(player.character_name, "cell_semi_perfect")
        player.ki = player.max_ki
        self.assertTrue(self.use(player, combat, "absorb_18"))
        self.run_frames(player, combat)
        self.assertEqual(player.character_name, "cell_perfect")
        self.assertNotIn("evolve", [t.kind for t in player.techniques])

    def test_the_cutscene_draws_the_partner_coming_and_a_flash(self):
        player, combat = self.fight("cell_imperfect")
        self.use(player, combat, "absorb_17")
        cutscene = combat.effects[-1]
        sizes = []
        for _ in range(evolution.ARRIVE + evolution.MEET + 10):
            self.clock.now += 17
            player.update_action()
            combat.update([], [])
            sizes.append(cutscene.image.get_size())
        self.assertTrue(all(w > 1 and h > 1 for w, h in sizes))

    def test_a_beaten_npc_cell_absorbs_by_itself(self):
        player, combat = self.fight("goku")
        cell = SaiyanNPC(260, 200, False, "cell_imperfect", 0, [], difficulty="normal")
        cell.update()
        cell.hp = cell.max_hp * 0.5
        cell.ki = cell.max_ki
        cell.next_technique_ms = 0
        cell.combat_engaged = True
        self.run_frames(player, combat, 300, npcs=[cell])
        self.assertEqual(cell.character_name, "cell_semi_perfect")
        self.assertEqual(cell.difficulty.name, "normal")  # still its difficulty

    def test_changing_map_mid_fusion_finishes_it(self):
        player, combat = self.fight("vegeta")
        self.use(player, combat, "potara")
        combat.clear_effects()
        self.assertEqual(player.character_name, "vegito")
        self.assertIsNone(player.action)


class OnlineEvolutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def test_the_other_game_sees_the_fusion(self):
        import online
        from test_online_match import FakeNet, fake_game
        use_average_stats(self)
        net = FakeNet()
        match = online.OnlineMatch(fake_game("goku"), net, {"slot": 0, "opponent": {
            "name": "Bob", "character": "vegeta"}})
        check = match.hit_check
        match.handle_messages([{"t": "state", "seq": 1, "x": 150, "y": 150, "character": "vegito"}])
        self.assertEqual(match.opponent.character_name, "vegito")
        self.assertEqual(match.opponent.bar_label, "Bob (Vegito)")
        self.assertIsNot(match.hit_check, check)  # what its hits can be is Vegito's now
        # A name that is no character is ignored
        match.handle_messages([{"t": "state", "seq": 2, "x": 150, "y": 150, "character": "../../etc"}])
        self.assertEqual(match.opponent.character_name, "vegito")


if __name__ == "__main__":
    unittest.main()
