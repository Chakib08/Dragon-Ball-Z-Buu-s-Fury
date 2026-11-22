"""Each arena has its own music (Config/arenas.json); the Cell Games theme
is the Cell Games arena's only."""

import os
import unittest

import pygame

import arenas
import epic
from map import MapManager, world_music
from saiyan import Saiyan
from utils.config import Config


class MusicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def test_every_arena_has_its_own_existing_music(self):
        ids = [entry["id"] for entry in arenas._load()]
        tracks = {arena: world_music(arena) for arena in ids}
        for arena, path in tracks.items():
            with self.subTest(arena=arena):
                self.assertTrue(os.path.exists(path), path)
        # All different
        self.assertEqual(len(set(tracks.values())), len(tracks))
        # The Cell Games theme only on the Cell Games arena
        cell = [arena for arena, path in tracks.items() if "Perfect-Cell" in path]
        self.assertEqual(cell, ["cell_games"])

    def test_a_fight_plays_its_arenas_music(self):
        for arena in ("kamis_lookout", "cell_games", "map"):
            if arena not in arenas.available():
                continue
            with self.subTest(arena=arena):
                manager = MapManager(pygame.display.get_surface(), Saiyan(0, 0, False, "goku"),
                                     arena_name=arena)
                self.assertEqual(manager.current_music, world_music(arena))

    def test_epic_fights_music_exists(self):
        for fight in epic.all_fights():
            if fight.music:
                with self.subTest(fight=fight.id):
                    from pathmanager import PathManager
                    self.assertTrue(os.path.exists(PathManager.soundtrack(fight.music)))


if __name__ == "__main__":
    unittest.main()
