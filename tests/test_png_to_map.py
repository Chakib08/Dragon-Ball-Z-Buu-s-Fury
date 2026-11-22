"""tools/png_to_map.py: a PNG picture into a map the game plays on."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytmx

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import png_to_map  # noqa: E402
from utils.config import Config  # noqa: E402
from average_stats import use_average_stats  # noqa: E402

GRASS, WATER, BRIDGE, ROCK = (96, 168, 64), (64, 120, 232), (160, 112, 64), (90, 90, 90)


def river_picture(path):
    """Grass, a river from top to bottom (x 144-192) and a bridge over it
    (y 96-128)."""
    picture = pygame.Surface((320, 240))
    picture.fill(GRASS)
    picture.fill(WATER, (144, 0, 48, 240))
    picture.fill(BRIDGE, (136, 96, 64, 32))
    pygame.image.save(picture, path)


def blocked_at(tmx, x, y):
    return any(obj.type == "collision" and obj.x <= x < obj.x + obj.width and obj.y <= y < obj.y + obj.height
               for obj in tmx.objects)


class PngToMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        self.folder = tempfile.mkdtemp()
        self.picture = os.path.join(self.folder, "arena.png")
        river_picture(self.picture)

    def convert(self, **options):
        summary = png_to_map.convert(self.picture, "arena", out_dir=self.folder, force=True, **options)
        return summary, pytmx.load_pygame(summary["map"])

    def test_water_is_blocked_but_not_the_bridge_and_the_points_are_free(self):
        summary, tmx = self.convert(water=True, preview=os.path.join(self.folder, "check.png"))
        self.assertEqual((tmx.width, tmx.height, tmx.tilewidth), (20, 15, 16))
        self.assertLessEqual(summary["tiles"], 12)  # identical tiles kept once
        self.assertTrue(blocked_at(tmx, 168, 40))       # the river
        self.assertFalse(blocked_at(tmx, 168, 112))     # the bridge over it
        self.assertFalse(blocked_at(tmx, 60, 60))       # grass
        self.assertTrue(blocked_at(tmx, -5, 100))       # the border
        spawn = tmx.get_object_by_name("spawn_world")
        self.assertFalse(blocked_at(tmx, spawn.x, spawn.y))
        for index in range(4):
            point = tmx.get_object_by_name(f"vegeta_path_{index}")
            feet = (point.x + 16, point.y + 32)
            self.assertFalse(blocked_at(tmx, *feet), index)
        self.assertTrue(os.path.exists(os.path.join(self.folder, "check.png")))

    def test_a_painted_mask_blocks_what_it_shows(self):
        mask = pygame.Surface((320, 240), pygame.SRCALPHA)
        mask.fill((0, 0, 0, 0))
        mask.fill((255, 0, 0, 255), (32, 32, 48, 48))  # a rock painted red
        mask_path = os.path.join(self.folder, "mask.png")
        pygame.image.save(mask, mask_path)
        _, tmx = self.convert(mask_path=mask_path)
        self.assertTrue(blocked_at(tmx, 50, 50))
        self.assertFalse(blocked_at(tmx, 168, 40))  # no --water: the river is not blocked

    def test_walkable_colours_block_everything_else(self):
        _, tmx = self.convert(walkable_colours=[GRASS, BRIDGE])
        self.assertTrue(blocked_at(tmx, 168, 40))
        self.assertFalse(blocked_at(tmx, 168, 112))
        self.assertFalse(blocked_at(tmx, 60, 60))

    def test_bad_inputs_are_refused(self):
        with self.assertRaises(ValueError):
            png_to_map.convert(self.picture, "../escape", out_dir=self.folder)
        png_to_map.convert(self.picture, "arena", out_dir=self.folder)
        with self.assertRaises(FileExistsError):
            png_to_map.convert(self.picture, "arena", out_dir=self.folder)
        with self.assertRaises(ValueError):  # all blocked: nowhere to stand
            png_to_map.convert(self.picture, "solid", out_dir=self.folder, block_colours=[GRASS, WATER, BRIDGE])

    def test_the_game_fights_on_it(self):
        from map import MapManager
        from saiyan import Saiyan
        use_average_stats(self)
        self.convert(water=True)
        original = __import__("pathmanager").PathManager.map_path.__func__

        def map_path(cls, name):
            return os.path.join(self.folder, "arena.tmx") if name == "arena" else original(cls, name)

        with patch.dict(Config.config_data, {"arena": "arena"}), \
                patch("pathmanager.PathManager.map_path", classmethod(map_path)):
            player = Saiyan(0, 0, False, "goku")
            manager = MapManager(pygame.display.get_surface(), player, enemies=("gohan", "vegeta"))
            game_map = manager.get_map()
            spawn = game_map.tmx_data.get_object_by_name("spawn_world")
            self.assertAlmostEqual(player.rect.midbottom[0], spawn.x, delta=1)
            self.assertEqual(game_map.portals, [])  # no house to enter here
            self.assertEqual(len(game_map.npcs), 2)
            for _ in range(60):
                manager.update()


if __name__ == "__main__":
    unittest.main()
