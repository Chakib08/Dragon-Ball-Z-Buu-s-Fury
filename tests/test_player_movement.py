import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from character import Character
from map import MapManager
from utils.config import Config


class PlayerMovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_diagonal_walk_is_normalized_and_preserves_previous_position(self):
        character = Character(10, 20, "goku")
        character.move("Walk Down", 4, (1, 1))

        self.assertAlmostEqual(character.position[0] - 10, 2 ** -0.5)
        self.assertAlmostEqual(character.position[1] - 20, 2 ** -0.5)
        self.assertEqual(character.old_position, [10, 20])

    def test_animation_and_facing_update_immediately_when_direction_changes(self):
        character = Character(10, 20, "goku")
        character.move("Walk Right", 4)

        self.assertEqual(character.animation_name, "Walk Right")
        self.assertEqual(character.facing, "Right")

        character.move("Walk Up", 4)
        self.assertEqual(character.animation_name, "Walk Up")
        self.assertEqual(character.facing, "Up")

    def test_all_roster_characters_support_movement_and_safe_attacks(self):
        for name in ("goku", "goten", "vegeta", "gohan"):
            with self.subTest(character=name):
                character = Character(10, 20, name)
                self.assertEqual(character.character_name, name)
                character.move("Walk Down", 4)
                character.move("Run Right", 4)
                for direction in ("Up", "Down", "Left", "Right"):
                    character.facing = direction
                    self.assertTrue(character.strike())
                    self.assertEqual(character.action["name"], "attack")

    def test_collision_resolution_keeps_unblocked_axis_movement(self):
        class FakeCharacter:
            def __init__(self):
                self.position = [12, 12]
                self.old_position = [10, 10]
                self.rect = pygame.Rect(10, 10, 20, 20)
                self.feet = pygame.Rect(0, 0, 10, 4)

            def update(self):
                self.rect.topleft = self.position
                self.feet.midbottom = self.rect.midbottom

            def save_location(self):
                self.old_position = self.position.copy()

        class FakeGroup:
            @staticmethod
            def sprites():
                return []

        manager = MapManager.__new__(MapManager)
        manager.current_map = "map"
        manager.transitioning = False
        manager.character = FakeCharacter()
        manager.maps = {
            "map": SimpleNamespace(
                portals=[],
                collisions=[pygame.Rect(26, 25, 4, 10)],
                group=FakeGroup(),
            )
        }

        manager.check_collisions()

        self.assertEqual(manager.character.position, [10, 12])
        self.assertEqual(manager.character.old_position, [10, 12])


if __name__ == "__main__":
    unittest.main()
