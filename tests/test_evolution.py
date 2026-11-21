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


class EvolutionCase(unittest.TestCase):
    """A fight to evolve in, with the clock in the test's hands."""

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


class EvolutionTests(EvolutionCase):
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

    def test_goku_and_vegeta_can_also_dance_into_gogeta(self):
        for name in ("goku", "vegeta"):
            with self.subTest(character=name):
                player, combat = self.fight(name)
                self.assertTrue(self.use(player, combat, "fusion_gogeta"))
                self.run_frames(player, combat)
                self.assertEqual(player.character_name, "gogeta")
                self.assertEqual(player.form, "ssj")  # always a Super Saiyan
                self.assertEqual(player.fusion["original"], name)
                # His time up: black hair (his own frames), then the split
                self.clock.now += 61_000
                combat.update([], [])
                self.assertIs(player.action["frames"][0], player.frame_image("Defuse 0"))
                self.run_frames(player, combat, 120)
                self.assertEqual(player.character_name, name)

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


class FusionTimeTests(EvolutionCase):
    """A fusion lasts a while, then the fighter is itself again."""

    def fuse(self, name, technique_id):
        player, combat = self.fight(name)
        self.assertTrue(self.use(player, combat, technique_id))
        self.run_frames(player, combat)
        return player, combat

    def test_goten_and_kid_trunks_dance_into_gotenks(self):
        for name in ("goten", "kid_trunks"):
            with self.subTest(character=name):
                player, combat = self.fuse(name, "fusion_dance")
                self.assertEqual(player.character_name, "gotenks")
                self.assertEqual(player.fusion["original"], name)

    def test_the_fusion_dance_uses_the_kids_own_glowing_frames(self):
        player, combat = self.fight("goten")
        self.use(player, combat, "fusion_dance")
        glowing = evolution.fusion_frames(player.animator, player.facing)
        self.assertTrue(glowing)
        self.assertTrue(any(frame is glowing[0] for frame in player.action["frames"]))

    def test_when_its_time_is_up_the_fusion_splits(self):
        player, combat = self.fuse("goku", "potara")
        self.assertEqual(player.character_name, "vegito")
        self.assertAlmostEqual(combat.fusion_left(player), 1.0, delta=0.1)
        player.hp = player.max_hp * 0.4
        # Half way: still Vegito, half the bar
        self.clock.now += 30_000
        combat.update([], [])
        self.assertEqual(player.character_name, "vegito")
        self.assertAlmostEqual(combat.fusion_left(player), 0.5, delta=0.05)
        # Time is up: powering down, a flash, Goku again with the same share of HP
        self.clock.now += 31_000
        self.run_frames(player, combat, 120)
        self.assertEqual(player.character_name, "goku")
        self.assertIsNone(player.fusion)
        self.assertIsNone(combat.fusion_left(player))
        self.assertAlmostEqual(player.hp / player.max_hp, 0.4)
        self.assertIsNone(player.action)
        self.assertEqual(combat.effects, [])
        self.assertIn("Potara Fusion (Vegito)", [t.name for t in player.techniques])

    def test_gotenks_powers_down_with_his_own_frames(self):
        player, combat = self.fuse("goten", "fusion_dance")
        self.assertEqual(player.form, "base")  # the dance makes base Gotenks
        player.set_form("ssj")  # gone Super Saiyan meanwhile
        self.clock.now += 61_000
        combat.update([], [])
        self.assertEqual(player.action["name"], "evolve")
        self.assertIs(player.action["frames"][0], player.frame_image("Defuse 0"))
        self.run_frames(player, combat, 120)
        self.assertEqual(player.character_name, "goten")

    def test_the_fusion_bar_shows_under_the_ki(self):
        player, combat = self.fuse("vegeta", "potara")
        drawn = []
        real = combat.hud._label
        combat.hud._label = lambda text, font, color=(255, 255, 255): drawn.append(text) or real(text, font, color)
        combat.draw(pygame.Surface((1200, 540)))
        self.assertIn("FU", drawn)
        self.assertEqual(combat.hud.ally_panel_top(), combat.hud.ALLY_PANEL_TOP + 20)

    def test_a_fused_npc_splits_too(self):
        player, combat = self.fight("vegeta")
        goten = SaiyanNPC(500, 500, False, "goten", 0, [], difficulty="normal")
        goten.update()
        goten.ki = goten.max_ki
        combat.start_evolution(goten, technique(goten, "fusion_dance"))
        self.run_frames(player, combat, 200, npcs=[goten])
        self.assertEqual(goten.character_name, "gotenks")
        self.clock.now += 61_000
        self.run_frames(player, combat, 120, npcs=[goten])
        self.assertEqual(goten.character_name, "goten")
        self.assertEqual(goten.difficulty.name, "normal")

    def test_no_fusing_again_for_90_seconds_after_a_fusion_ends(self):
        player, combat = self.fuse("goku", "potara")
        self.clock.now += 61_000
        self.run_frames(player, combat, 120)  # it splits
        self.assertEqual(player.character_name, "goku")
        player.ki = player.max_ki
        for technique_id in ("potara", "fusion_gogeta"):
            self.assertFalse(self.use(player, combat, technique_id))  # either fusion
        self.assertAlmostEqual(combat.fusion_cooldown_left(player), 1.0, delta=0.05)
        drawn = []
        real = combat.hud._label
        combat.hud._label = lambda text, font, color=(255, 255, 255): drawn.append(text) or real(text, font, color)
        combat.draw(pygame.Surface((1200, 540)))
        self.assertIn("CD", drawn)
        self.assertTrue(any(" (in 90 s)" in text for text in drawn))  # the selected fusion's wait
        self.clock.now += 89_000
        self.assertFalse(self.use(player, combat, "potara"))
        self.clock.now += 2_000
        self.assertIsNone(combat.fusion_cooldown_left(player))
        self.assertTrue(self.use(player, combat, "potara"))

    def test_a_cooling_down_npc_does_not_try_to_fuse(self):
        player, combat = self.fight("vegeta")
        goten = SaiyanNPC(500, 500, False, "goten", 0, [], difficulty="normal")
        goten.update()
        goten.hp = goten.max_hp * 0.3
        goten.fusion_cooldown = {"ends_ms": self.clock.now + 90_000, "total_ms": 90_000}
        dance = technique(goten, "fusion_dance")
        self.assertFalse(combat.ai.technique_fits(goten, dance, player))
        goten.fusion_cooldown = None
        self.assertTrue(combat.ai.technique_fits(goten, dance, player))

    def test_an_absorption_is_for_good(self):
        player, combat = self.fuse("cell_imperfect", "absorb_17")
        self.assertIsNone(player.fusion)
        self.clock.now += 10 ** 6
        self.run_frames(player, combat, 60)
        self.assertEqual(player.character_name, "cell_semi_perfect")

    def test_changing_map_while_it_splits_finishes_the_split(self):
        player, combat = self.fuse("goku", "potara")
        self.clock.now += 61_000
        combat.update([], [])
        combat.clear_effects()
        self.assertEqual(player.character_name, "goku")
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
