import json
import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from animation import Animation
from utils.config import Config

ROSTER = ("goku", "goten", "vegeta", "gohan")
# Sprite sheets ripped with a teal background; frames sit in (0, 64, 64) cells
SHEET_BACKGROUND = (0, 128, 128)
DIRECTIONS = ("Up", "Down", "Left", "Right")


class CharacterConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((100, 100))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_every_roster_character_has_all_required_animations(self):
        for name in ROSTER:
            animation = Animation(name)
            required = [f"IDLE {d}" for d in DIRECTIONS]
            for direction in DIRECTIONS:
                required += [f"Walk {direction} {i}" for i in range(4)]
                required += [f"Run {direction} {i}" for i in range(4)]
                required += [f"Attack {direction} {i}" for i in range(12)]
            for animation_name in required:
                with self.subTest(character=name, animation=animation_name):
                    self.assertTrue(animation.has_animation(animation_name))
                    image = animation.get_image_by_animation_name(animation_name)
                    self.assertGreater(image.get_width(), 0)

    def test_frames_stay_inside_their_sprite_cell(self):
        """A frame that crosses the cell border shows the teal sheet background
        or a piece of the neighbour frame (garbled sprite)."""
        for name in ("goten", "vegeta", "gohan"):
            animation = Animation(name)
            sheet = animation.sprit_sheet
            for frame in animation.animations:
                with self.subTest(character=name, animation=frame["AnimationName"]):
                    size = frame["Size"]
                    rect = pygame.Rect(frame["x"], frame["y"], size["Width"], size["Height"])
                    self.assertTrue(sheet.get_rect().contains(rect))
                    crop = sheet.subsurface(rect)
                    mask = pygame.mask.from_threshold(crop, SHEET_BACKGROUND, (1, 1, 1, 255))
                    self.assertEqual(mask.count(), 0)

    def test_frame_background_matches_the_sheet_cell_color(self):
        for name in ("goten", "vegeta", "gohan"):
            animation = Animation(name)
            for frame in animation.animations:
                with self.subTest(character=name, animation=frame["AnimationName"]):
                    self.assertEqual(
                        (frame["Background"]["R"], frame["Background"]["G"], frame["Background"]["B"]),
                        (0, 64, 64),
                    )

    def test_character_name_matches_folder_and_sheet(self):
        for name in ROSTER:
            with open(os.path.join(Config.CONFIG_DIR, name, "base.json")) as file:
                data = json.load(file)
            self.assertEqual(data["Character"], name)
            self.assertTrue(os.path.exists(os.path.join(Config.ROOT_DIR, data["Image path"])))

    def test_left_animations_mirror_the_right_ones(self):
        for name in ROSTER:
            animation = Animation(name)
            for macro in ("IDLE", "Walk 0", "Run 0", "Attack 0"):
                parts = macro.split()
                right = " ".join([parts[0], "Right"] + parts[1:])
                left = " ".join([parts[0], "Left"] + parts[1:])
                with self.subTest(character=name, animation=macro):
                    a, b = animation.get_animation_by_name(right), animation.get_animation_by_name(left)
                    self.assertEqual((a["x"], a["y"], a["Size"]), (b["x"], b["y"], b["Size"]))


if __name__ == "__main__":
    unittest.main()
