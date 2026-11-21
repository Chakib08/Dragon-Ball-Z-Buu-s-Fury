"""Arenas: built from map pictures, chosen after the teams, fought on in
arcade and online (arenas.py, tools/build_arenas.py)."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import arenas  # noqa: E402
import png_to_map  # noqa: E402
from menu import Menu, State  # noqa: E402
from utils.config import Config  # noqa: E402
from average_stats import use_average_stats  # noqa: E402

GRASS, WATER = (96, 168, 64), (64, 120, 232)


class ArenaCase(unittest.TestCase):
    """A built arena "test_arena" (grass, a lake on the left) in a
    temporary folder the game finds its arenas in."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))
        cls.folder = tempfile.mkdtemp()
        picture = pygame.Surface((640, 480))
        picture.fill((71, 255, 187))  # a rip's mint background around the area
        picture.fill(GRASS, (40, 40, 480, 320))
        picture.fill(WATER, (40, 40, 80, 320))
        path = os.path.join(cls.folder, "rip.png")
        pygame.image.save(picture, path)
        png_to_map.convert(path, "test_arena", out_dir=cls.folder, crop=(20, 20, 520, 360), water=True,
                           block_colours=[(71, 255, 187)], walk_areas=[(40, 40, 520, 360)],
                           thumbnail=os.path.join(cls.folder, "test_arena_thumb.png"))

    def setUp(self):
        use_average_stats(self)
        entries = [{"id": "map", "name": "Goku's Home", "builtin": True},
                   {"id": "test_arena", "name": "Test Arena", "source": "rip"},
                   {"id": "not_built", "name": "Not Built", "source": "missing"}]
        for patcher in (patch("arenas.arenas_dir", return_value=self.folder),
                        patch("arenas._entries", entries)):
            patcher.start()
            self.addCleanup(patcher.stop)


class ArenaTests(ArenaCase):
    def test_only_built_arenas_are_offered(self):
        self.assertEqual(arenas.available(), ("map", "test_arena"))
        self.assertEqual(arenas.name("test_arena"), "Test Arena")
        self.assertIsNotNone(arenas.thumbnail("test_arena"))

    def test_the_arena_comes_after_the_opponents_and_starts_the_fight(self):
        resolution = (1200, 540)
        screen = pygame.Surface(resolution)
        key = lambda code: pygame.event.Event(pygame.KEYDOWN, key=code)
        menu = Menu(resolution)
        menu.state = State.ENEMY_SELECT
        menu.launch_menu(screen, resolution, [key(pygame.K_RETURN)])
        self.assertEqual(menu.state, State.MAP_SELECT)
        menu.launch_menu(screen, resolution, [])
        self.assertEqual(set(menu.arena_rects), {"map", "test_arena"})
        menu.launch_menu(screen, resolution, [key(pygame.K_RIGHT)])
        self.assertEqual(menu.selected_arena, "test_arena")
        self.assertFalse(menu.isPlaying)
        menu.launch_menu(screen, resolution, [key(pygame.K_RETURN)])
        self.assertTrue(menu.isPlaying)

    def test_an_arcade_fight_happens_on_the_chosen_arena(self):
        from game import Game
        game = Game((1200, 540), "test", fullscreen=False)
        game.menu = Menu(game.resolution)
        game.menu.selected_arena = "test_arena"
        game.menu.selected_enemies = ["gohan", "vegeta"]
        game.start_story()
        game_map = game.map_manager.get_map()
        self.assertEqual(game.map_manager.world_file, "test_arena")
        spawn = game_map.get_object("spawn_world")
        self.assertAlmostEqual(game.character.rect.midbottom[0], spawn.x, delta=1)
        self.assertEqual(game_map.portals, [])
        self.assertEqual(len(game_map.npcs), 2)
        # The lake is blocked
        self.assertTrue(any(rect.collidepoint(40, 100) for rect in game_map.collisions))
        for _ in range(30):
            game.loop_once([])

    def test_a_missing_arena_falls_back_to_gokus_home(self):
        from map import MapManager
        from saiyan import Saiyan
        manager = MapManager(pygame.display.get_surface(), Saiyan(0, 0, False, "goku"), arena_name="not_built")
        self.assertEqual(manager.world_file, "map")


class OnlineArenaTests(ArenaCase):
    def test_both_players_fight_on_the_hosts_arena_on_its_two_spawns(self):
        import online
        from test_online_match import FakeNet, fake_game
        net_a, net_b = FakeNet(), FakeNet()
        a = online.OnlineMatch(fake_game("goku"), net_a, {"slot": 0, "map": "test_arena",
                                                          "opponent": {"character": "vegeta"}})
        b = online.OnlineMatch(fake_game("vegeta"), net_b, {"slot": 1, "map": "test_arena",
                                                            "opponent": {"character": "goku"}})
        for match in (a, b):
            self.assertEqual(match.arena, "test_arena")
        game_map = a.game.map_manager.get_map()
        spawn, rival = game_map.get_object("spawn_world"), game_map.get_object("spawn_rival")
        self.assertAlmostEqual(a.player.rect.midbottom[0], spawn.x, delta=1)
        self.assertAlmostEqual(b.player.rect.midbottom[0], rival.x, delta=1)
        self.assertEqual((a.player.facing, b.player.facing), ("Right", "Left"))
        # Each sees the other where it really is
        self.assertAlmostEqual(a.opponent.position[0], b.player.position[0], delta=1)

    def test_an_arena_this_game_lacks_is_goku_s_home(self):
        import online
        from test_online_match import FakeNet, fake_game
        match = online.OnlineMatch(fake_game("goku"), FakeNet(), {"slot": 0, "map": "../../etc",
                                                                  "opponent": {"character": "vegeta"}})
        self.assertEqual(match.arena, "map")

    def test_the_lobby_creates_rooms_on_its_arena_and_shows_theirs(self):
        import online
        from test_online_match import FakeNet
        net = FakeNet()
        net.connect = lambda host, port: None
        lobby = online.LobbyScreen(net, (1200, 540), "goku", name="Chakib", arena="test_arena")
        lobby.create_room("1v1")
        self.assertEqual(net.sent[-1]["map"], "test_arena")
        self.assertEqual(lobby.room_label({"host": "Bob", "character": "vegeta", "mode": "1v1",
                                           "map": "test_arena"}), "1v1: Bob (Vegeta) - Test Arena")


class ServerArenaTests(unittest.TestCase):
    def test_a_room_keeps_its_arena_and_refuses_odd_names(self):
        sys.path.insert(0, os.path.join(ROOT, "server"))
        import lobby_server
        self.assertEqual(lobby_server.Room(1, None, "1v1", "kamis_lookout").map, "kamis_lookout")
        self.assertEqual(lobby_server.Room(1, None, "1v1", "../../x").map, "map")
        self.assertEqual(lobby_server.Room(1, None, "1v1", None).map, "map")


if __name__ == "__main__":
    unittest.main()
