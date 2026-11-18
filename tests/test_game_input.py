import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import game
from game import Game
from utils.config import Config


def key_down(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code)


class AttackInputTests(unittest.TestCase):
    """One attack per press of the attack button (keyboard or on screen)."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.now = 10000
        patcher = patch("pygame.time.get_ticks", side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.game = Game((1200, 1000), "test")
        self.player = self.game.character
        self.combat = self.game.map_manager.combat
        self.enemy = self.game.map_manager.get_map().npcs[0]
        self.enemy.update()
        # Feet 15 map pixels left of the enemy's: within reach
        self.player.position = [self.enemy.feet.centerx - 15 - self.player.rect.width / 2,
                                self.enemy.position[1] + self.enemy.rect.height - self.player.rect.height]
        self.player.save_location()
        self.player.update()
        self.player.facing = "Right"

    def frame(self, events=(), ms=17):
        self.now += ms
        self.game.play_frame(list(events), False)

    def frames(self, count):
        swings = 0
        for _ in range(count):
            self.frame()
            swings += self.combat.player_swung
        return swings

    def test_one_press_is_one_attack_even_if_the_key_stays_down(self):
        self.frame([key_down(pygame.K_a)])
        self.assertTrue(self.combat.player_swung)
        self.assertEqual(self.player.action["name"], "attack")
        self.assertLess(self.enemy.hp, self.enemy.max_hp)

        held = {pygame.K_a: True}
        with patch("pygame.key.get_pressed", return_value=_Keys(held)):
            self.assertEqual(self.frames(200), 0)

    def test_touch_button_attacks_once_per_tap(self):
        x, y = self.game.touch_controls.buttons["attack"]
        tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(round(x), round(y)))
        self.frame([tap])
        self.assertTrue(self.combat.player_swung)
        # Finger still on the button: no second attack
        self.assertEqual(self.frames(200), 0)

    def test_mashing_attacks_at_the_shared_attack_pace(self):
        swings = 0
        duration_ms = 5 * self.player.ATTACK_COOLDOWN_MS
        for index in range(duration_ms // 17):
            self.frame([key_down(pygame.K_a)] if index % 6 == 0 else [])
            swings += self.combat.player_swung
        self.assertIn(swings, (5, 6))

    def test_a_press_just_before_the_strike_is_ready_still_counts(self):
        self.frame([key_down(pygame.K_a)])
        # Pressed again while the first punch is still playing
        self.frames(12)
        self.frame([key_down(pygame.K_a)])
        self.assertFalse(self.combat.player_swung)
        self.assertEqual(self.frames(20), 1)

    def test_an_old_press_is_forgotten(self):
        self.game.attack_pressed_ms = self.now
        self.assertTrue(self.game.attack_requested)
        self.now += game.ATTACK_BUFFER_MS + 1
        self.assertFalse(self.game.attack_requested)

    def test_each_press_plays_a_different_move(self):
        # A hit from the enemy would make the player flinch and drop a press
        self.enemy.attack_damage = 0
        seen = []
        for _ in range(4):
            self.frame([key_down(pygame.K_a)])
            self.assertTrue(self.combat.player_swung)
            seen.append(self.player.action["frames"])
            self.frames(40)
        self.assertEqual(self.player.attack_move_index, 4)
        self.assertIsNot(seen[0], seen[1])


    def test_stick_moves_the_player_and_runs_when_pushed_far(self):
        controls = self.game.touch_controls
        cx, cy = controls.stick_center
        r = controls.stick_radius
        down = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(round(cx), round(cy)))
        self.frame([down])
        start = list(self.player.position)
        # Half way down-left: walk diagonally
        drag = pygame.event.Event(pygame.MOUSEMOTION, pos=(round(cx - r * 0.4), round(cy + r * 0.4)), buttons=(1, 0, 0))
        self.player.position = [60, 300]
        self.player.save_location()
        self.frame([drag])
        self.frames(10)
        self.assertTrue(self.player.animation_name.startswith("Walk"))
        # Pushed to the edge: run
        push = pygame.event.Event(pygame.MOUSEMOTION, pos=(round(cx + r), round(cy)), buttons=(1, 0, 0))
        self.frame([push])
        self.assertEqual(self.player.animation_name, "Run Right")
        self.assertEqual(self.player.facing, "Right")


    def test_holding_block_guards_and_stops_moving_and_attacking(self):
        x, y = self.game.touch_controls.buttons["block"]
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(round(x), round(y)))])
        self.assertTrue(self.player.blocking)
        start = list(self.player.position)
        with patch("pygame.key.get_pressed", return_value=_Keys({pygame.K_RIGHT: True})):
            self.frame([key_down(pygame.K_a)])
            self.frames(5)
        self.assertEqual(self.player.position, start)
        self.assertFalse(self.combat.player_swung)
        self.frame([pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(round(x), round(y)))])
        self.assertFalse(self.player.blocking)

    def test_f_key_blocks(self):
        with patch("pygame.key.get_pressed", return_value=_Keys({pygame.K_f: True})):
            self.frame()
        self.assertTrue(self.player.blocking)
        self.frame()
        self.assertFalse(self.player.blocking)


    def test_every_hit_shows_the_hurt_animation(self):
        for _ in range(4):
            self.player.take_damage(1, self.enemy.feet.center)
            self.assertEqual(self.player.action["name"], "hurt")
            self.frames(30)

    def test_attacking_or_guarding_cancels_the_hurt_animation(self):
        self.enemy.attack_damage = 0
        self.player.take_damage(1)
        self.frame([key_down(pygame.K_a)])
        self.assertTrue(self.combat.player_swung)
        self.assertEqual(self.player.action["name"], "attack")

        self.frames(40)
        self.player.take_damage(1)
        with patch("pygame.key.get_pressed", return_value=_Keys({pygame.K_f: True})):
            self.frame()
        self.assertTrue(self.player.blocking)
        self.assertIsNone(self.player.action)


    def test_holding_d_charges_and_letting_go_fires(self):
        combat = self.combat
        combat.selected_technique = 1  # Kamehameha
        self.enemy.attack_damage = 0
        with patch("pygame.key.get_pressed", return_value=_Keys({pygame.K_d: True})):
            self.frame([key_down(pygame.K_d)])
            self.frames(30)
        self.assertTrue(combat.charging)
        self.assertGreater(combat.charge_level, 0.2)
        self.frame()  # key released
        self.assertFalse(combat.charging)
        self.assertEqual(self.player.action["name"], "special")


class _Keys:
    def __init__(self, held):
        self.held = held

    def __getitem__(self, key):
        return self.held.get(key, False)


if __name__ == "__main__":
    unittest.main()
