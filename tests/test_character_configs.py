import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from animation import Animation
from utils.config import Config

ROSTER = ("goku", "vegeta", "gohan")
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

    def required_animations(self):
        required = [f"IDLE {d}" for d in DIRECTIONS]
        for direction in DIRECTIONS:
            required += [f"Walk {direction} {i}" for i in range(4)]
            required += [f"Run {direction} {i}" for i in range(4)]
            required += [f"Attack {direction} {i}" for i in range(12)]
            required += [f"Hurt {direction} {i}" for i in range(2)]
            required += [f"Special {direction} {i}" for i in range(2)]
        return required

    def test_every_downloaded_form_has_all_required_animations(self):
        for name in ROSTER:
            animation = Animation(name)
            self.assertTrue(animation.forms, name)
            for form_name, form in animation.forms.items():
                for animation_name in self.required_animations():
                    with self.subTest(character=name, form=form_name, animation=animation_name):
                        self.assertTrue(form.has(animation_name))
                        self.assertGreater(form.image(animation_name).get_width(), 0)

    def test_frames_stay_inside_their_sheet(self):
        for name in ROSTER:
            for form_name, form in Animation(name).forms.items():
                for frame in form.animations:
                    with self.subTest(character=name, form=form_name, animation=frame["AnimationName"]):
                        size = frame["Size"]
                        rect = pygame.Rect(frame["x"], frame["y"], size["Width"], size["Height"])
                        self.assertTrue(form.sheet.get_rect().contains(rect))

    def test_characters_with_both_forms_can_play_the_transformation(self):
        for name in ROSTER:
            animation = Animation(name)
            if animation.has_form("base") and animation.has_form("ssj"):
                with self.subTest(character=name):
                    self.assertGreaterEqual(animation.frame_count("Transform"), 4)

    def test_vegeta_only_exists_as_a_super_saiyan(self):
        vegeta = Animation("vegeta")
        self.assertEqual(list(vegeta.forms), ["ssj"])
        self.assertEqual(vegeta.form, "ssj")

    def test_a_form_whose_sheet_was_not_downloaded_is_skipped(self):
        with patch("animation.SpriteForm.sheet_exists", side_effect=lambda path: "base" in path):
            goku = Animation("goku")
        self.assertEqual(list(goku.forms), ["base"])
        with patch("animation.SpriteForm.sheet_exists", return_value=False):
            with self.assertRaises(FileNotFoundError):
                Animation("goku")

    def test_frame_background_is_the_colour_around_the_sprite(self):
        """The colour made transparent must be the one framing the sprite,
        whatever background the downloaded sheet uses."""
        for name in ROSTER:
            animation = Animation(name)
            for form in animation.forms.values():
                sheet = form.sheet
                for frame in form.animations:
                    with self.subTest(character=name, animation=frame["AnimationName"]):
                        size = frame["Size"]
                        crop = sheet.subsurface(
                            pygame.Rect(frame["x"], frame["y"], size["Width"], size["Height"])
                        )
                        width, height = crop.get_size()
                        border = [crop.get_at((x, y))[:3] for x in range(width) for y in (0, height - 1)]
                        border += [crop.get_at((x, y))[:3] for y in range(height) for x in (0, width - 1)]
                        background = frame["Background"]
                        self.assertEqual(
                            max(set(border), key=border.count),
                            (background["R"], background["G"], background["B"]),
                        )

    def test_frames_are_cut_once_and_shared_between_sprites(self):
        first, second = Animation("vegeta"), Animation("vegeta")
        self.assertIs(first.forms["ssj"], second.forms["ssj"])
        image = first.get_image_by_animation_name("IDLE Right")
        self.assertIs(image, second.get_image_by_animation_name("IDLE Right"))
        mirrored = first.get_image_by_animation_name("IDLE Right", flipped=True)
        self.assertIsNot(mirrored, image)
        self.assertIs(mirrored, first.get_image_by_animation_name("IDLE Right", flipped=True))
        self.assertEqual(first.get_frames("Walk Left", 4), second.get_frames("Walk Left", 4))

    def test_character_name_matches_folder_and_sheet(self):
        for name in ROSTER:
            for form in ("base", "ssj"):
                path = os.path.join(Config.CONFIG_DIR, name, f"{form}.json")
                if not os.path.exists(path):
                    continue
                with open(path) as file:
                    data = json.load(file)
                with self.subTest(character=name, form=form):
                    self.assertEqual(data["Character"], name)
                    # Sheets live next to each other in the character's folder
                    self.assertTrue(data["Image path"].startswith(f"Graphics/assets/{name}/"))

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
