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
        self.player.position = [self.enemy.position[0] - 22, self.enemy.position[1]]
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
        seen = []
        for _ in range(4):
            self.frame([key_down(pygame.K_a)])
            self.assertTrue(self.combat.player_swung)
            seen.append(self.player.action["frames"])
            self.frames(40)
        self.assertEqual(self.player.attack_move_index, 4)
        self.assertIsNot(seen[0], seen[1])


class _Keys:
    def __init__(self, held):
        self.held = held

    def __getitem__(self, key):
        return self.held.get(key, False)


if __name__ == "__main__":
    unittest.main()
