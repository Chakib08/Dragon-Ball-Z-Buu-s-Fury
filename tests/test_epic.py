"""Epic Fights (epic.py): the fights, the menu, waves, the next fight, and
playing one online (each player on a side)."""

import os
import tempfile
import unittest
from unittest.mock import patch

import pygame

import epic
import settings
from menu import Menu, State
from npc import HEROES
from utils.config import Config
from average_stats import steady_module_fixtures

setUpModule, tearDownModule = steady_module_fixtures()


def key(k):
    return pygame.event.Event(pygame.KEYDOWN, key=k)


class EpicCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))
        epic.reset()
        if not epic.fights():
            raise unittest.SkipTest("characters not installed (setup.sh)")

    def setUp(self):
        # The cleared fights go to a file of the test's own
        folder = tempfile.mkdtemp()
        path = os.path.join(folder, "user_settings.json")
        patcher = patch.object(settings, "settings_path", return_value=path)
        patcher.start()
        self.addCleanup(patcher.stop)


class FightListTests(EpicCase):
    def test_every_fight_is_playable_here(self):
        # All of the file's fights: their characters and arenas are installed
        self.assertEqual([f.id for f in epic.fights()], [f.id for f in epic.all_fights()])
        self.assertGreaterEqual(len(epic.fights()), 10)
        ids = [f.id for f in epic.fights()]
        self.assertEqual(len(ids), len(set(ids)))
        for fight in epic.fights():
            with self.subTest(fight=fight.id):
                self.assertTrue(fight.intro)
                self.assertTrue(all(len(wave) <= epic.MAX_WAVE for wave in fight.waves))

    def test_the_asked_for_fights_are_there(self):
        matchups = {(f.hero, f.form, f.boss) for f in epic.fights()}
        self.assertIn(("gohan_teen", "ssj2", "cell_perfect"), matchups)
        self.assertIn(("vegito", "ssj", "super_buu_gohan"), matchups)
        self.assertIn(("goku", "ssj3", "kid_buu"), matchups)
        self.assertIn(("goku_log2", None, "frieza"), matchups)
        juniors = epic.by_id("cell_juniors")
        self.assertEqual(juniors.waves, [["cell_jr"] * 7])
        self.assertEqual((juniors.hero, juniors.form), ("goku", "ssj"))
        self.assertEqual(juniors.allies, ["vegeta_log2", "trunks_future", "piccolo", "tien", "yamcha", "krillin"])
        self.assertEqual(epic.by_id("goku_black").boss, "goku_black")

    def test_sides(self):
        fight = epic.by_id("android13")
        self.assertEqual(fight.side(0), ("goku_log2", None, ["vegeta_log2", "trunks_future"]))
        self.assertEqual(fight.side(1), ("android19", None, ["android20"]))

    def test_cleared_fights_are_remembered(self):
        fight = epic.by_id("namek")
        self.assertNotIn("namek", epic.cleared())
        epic.mark_cleared(fight)
        self.assertIn("namek", epic.cleared())
        self.assertEqual(epic.next_fight(fight).id, "cooler")
        self.assertIsNone(epic.next_fight(epic.fights()[-1]))


class EpicMenuTests(EpicCase):
    def menu(self):
        menu = Menu((1200, 540))
        screen = pygame.Surface((1200, 540))
        return menu, lambda events: menu.launch_menu(screen, (1200, 540), events)

    def test_the_story_entry_lists_the_fights(self):
        menu, run = self.menu()
        menu.selected_item = [item for item, _, _ in Menu.MAIN_ITEMS].index("epic")
        run([key(pygame.K_RETURN)])
        self.assertEqual(menu.state, State.EPIC_SELECT)
        run([])
        self.assertTrue(menu.epic_rows)
        run([key(pygame.K_DOWN), key(pygame.K_DOWN)])
        self.assertEqual(menu.epic_focus, 2)
        run([key(pygame.K_RETURN)])
        self.assertTrue(menu.isPlaying)
        self.assertFalse(menu.online)
        self.assertEqual(menu.epic.id, epic.fights()[2].id)

    def test_a_fight_can_be_taken_online(self):
        menu, run = self.menu()
        menu.state = State.EPIC_SELECT
        run([key(pygame.K_o)])
        self.assertEqual(menu.state, State.NAME_ENTRY)
        self.assertTrue(menu.online)
        with patch("menu.user_settings.load", return_value={}), patch("menu.user_settings.save"):
            menu.player_name = "Tester"
            menu.confirm_name()
        # The fight decides the teams: straight to the lobby
        self.assertTrue(menu.isPlaying)
        fight = epic.fights()[0]
        self.assertEqual(menu.selected_character, fight.hero)
        self.assertEqual(menu.selected_arena, fight.arena)

    def test_back(self):
        menu, run = self.menu()
        menu.state = State.EPIC_SELECT
        run([key(pygame.K_ESCAPE)])
        self.assertEqual(menu.state, State.START)
        menu.state = State.EPIC_SELECT
        run([key(pygame.K_o)])
        menu.go_back()
        self.assertEqual(menu.state, State.EPIC_SELECT)
        self.assertFalse(menu.online)


class EpicGameTests(EpicCase):
    def game(self, fight_id):
        from game import Game
        game = Game((1200, 540), "test", fullscreen=False)
        game.menu = Menu(game.resolution)
        game.menu.epic = epic.by_id(fight_id)
        game.start_story()
        return game

    def enemies(self, game):
        return [npc for npc in game.map_manager.get_map().npcs if npc.team != HEROES]

    def beat(self, enemies):
        for npc in enemies:
            npc.hp = 0
            npc.faint()
            npc.faint_finished = True

    def test_the_fight_starts_as_told(self):
        game = self.game("cell_games")
        self.assertEqual(game.character.character_name, "gohan_teen")
        self.assertEqual(game.character.form, "ssj2")
        self.assertEqual([npc.character_name for npc in self.enemies(game)], ["cell_perfect"])
        self.assertEqual(game.map_manager.world_file, "cell_games")
        self.assertTrue(game.map_manager.current_music.endswith("DBZ-Perfect-Cell-Theme.wav"))
        # The versus card first, then the fight
        story = game.scenes["story"]
        self.assertIsNotNone(story.intro)
        story.intro.shown_at -= 10_000
        game.loop_once([key(pygame.K_RETURN)])
        self.assertIsNone(story.intro)

    def test_a_boss_can_start_transformed(self):
        game = self.game("goku_black")
        boss = self.enemies(game)[0]
        self.assertEqual(boss.character_name, "goku_black")
        self.assertEqual(boss.form, "ssj")
        self.assertEqual(sorted(npc.character_name for npc in game.map_manager.get_map().npcs
                                if npc.team == HEROES), ["vegeta"])

    def test_seven_against_seven(self):
        game = self.game("cell_juniors")
        npcs = game.map_manager.get_map().npcs
        self.assertEqual((game.character.character_name, game.character.form), ("goku", "ssj"))
        allies = {npc.character_name: npc.form for npc in npcs if npc.team == HEROES}
        self.assertEqual(allies, {"vegeta_log2": "ssj", "trunks_future": "ssj", "piccolo": "base",
                                  "tien": "base", "yamcha": "base", "krillin": "base"})
        self.assertEqual([npc.character_name for npc in self.enemies(game)], ["cell_jr"] * 7)
        # Nobody stands in someone else
        bodies = [game.character.body, *(npc.body for npc in npcs)]
        overlapping = sum(1 for i, a in enumerate(bodies) for b in bodies[i + 1:] if a.colliderect(b))
        self.assertLessEqual(overlapping, 2)
        for _ in range(60):
            game.loop_once([])

    def test_a_cell_jr_explodes_and_vanishes_when_knocked_out(self):
        from effects import Explosion
        game = self.game("cell_juniors")
        game.scenes["story"].intro = None
        junior = self.enemies(game)[0]
        group = game.map_manager.get_map().group
        self.assertIn(junior, group)
        junior.take_damage(10_000)
        game.loop_once([])
        explosions = [e for e in game.map_manager.combat.effects if isinstance(e, Explosion)]
        self.assertEqual(len(explosions), 1)
        self.assertTrue(junior.vanished and junior.faint_finished)
        game.loop_once([])
        self.assertNotIn(junior, group)  # gone from the map
        for _ in range(60):
            game.loop_once([])
        self.assertNotIn(explosions[0], game.map_manager.combat.effects)
        # The others knocked out the usual way still lie on the ground
        from game import Game
        other = Game((1200, 540), "test", fullscreen=False)
        other.menu = Menu(other.resolution)
        other.start_story()
        gohan = self.enemies(other)[0]
        gohan.take_damage(10_000)
        other.loop_once([])
        self.assertFalse(getattr(gohan, "vanished", False))
        self.assertIn(gohan, other.map_manager.get_map().group)

    def test_arcade_keeps_its_limits(self):
        from game import Game
        game = Game((1200, 540), "test", fullscreen=False)
        game.menu = Menu(game.resolution)
        game.menu.selected_enemies = ["cell_jr"] * 7
        game.menu.selected_allies = ["krillin", "tien", "yamcha", "piccolo"]
        game.start_story()
        npcs = game.map_manager.get_map().npcs
        self.assertEqual(len([n for n in npcs if n.team == HEROES]), 3)
        self.assertEqual(len([n for n in npcs if n.team != HEROES]), 4)

    def test_waves_then_victory_then_the_next_fight(self):
        game = self.game("android13")
        story = game.scenes["story"]
        story.intro = None
        first = self.enemies(game)
        self.assertEqual([npc.character_name for npc in first], ["android19", "android20"])
        self.beat(first)
        game.loop_once([])
        # The second wave arrives instead of the victory
        self.assertIsNone(story.result)
        self.assertIsNotNone(story.banner)
        alive = [npc for npc in self.enemies(game) if npc.hp > 0]
        self.assertEqual([npc.character_name for npc in alive], ["android13"])
        self.beat(alive)
        game.loop_once([])
        self.assertIsNotNone(story.result)
        self.assertTrue(story.result.victory)
        self.assertIn("android13", epic.cleared())
        self.assertEqual(story.result.retry_label, "Next fight")
        # On to the next fight
        game.loop_once([key(pygame.K_RETURN)])
        self.assertEqual(game.menu.epic.id, epic.next_fight(epic.by_id("android13")).id)
        self.assertEqual(game.character.character_name, game.menu.epic.hero)
        self.assertIsNotNone(story.intro)

    def test_losing_offers_a_retry_of_the_same_fight(self):
        game = self.game("namek")
        story = game.scenes["story"]
        story.intro = None
        game.character.hp = 0
        game.character.faint_finished = True
        game.loop_once([])
        self.assertFalse(story.result.victory)
        self.assertEqual(story.result.retry_label, "Retry")
        game.loop_once([key(pygame.K_RETURN)])
        self.assertEqual(game.menu.epic.id, "namek")

    def test_arcade_is_unchanged(self):
        from game import Game
        game = Game((1200, 540), "test", fullscreen=False)
        game.menu = Menu(game.resolution)
        game.start_story()
        self.assertIsNone(game.scenes["story"].intro)
        self.assertFalse(game.next_wave())


class EpicOnlineTests(EpicCase):
    def test_each_player_plays_a_side(self):
        import online
        from test_online_match import FakeNet, fake_game
        net_a, net_b = FakeNet(), FakeNet()
        net_a.peer, net_b.peer = net_b, net_a
        # Whatever they had picked, the fight decides
        host = online.OnlineMatch(fake_game("goku"), net_a, {"slot": 0, "mode": "team", "epic": "goku_black",
                                                             "opponent": {"character": "broly"}})
        self.assertEqual(host.player.character_name, "trunks_future")
        self.assertEqual(host.player.form, "ssj")
        self.assertEqual([a.character_name for a in host.allies], ["vegeta"])
        self.assertEqual(host.opponent.character_name, "goku_black")
        self.assertEqual(host.arena, "capsule_corp")
        guest = online.OnlineMatch(fake_game("vegeta"), net_b, {"slot": 1, "mode": "team", "epic": "goku_black",
                                                                "opponent": {"character": "goku"}})
        self.assertEqual(guest.player.character_name, "goku_black")
        self.assertEqual(guest.player.form, "ssj")  # Rosé
        self.assertEqual(guest.opponent.character_name, "trunks_future")
        self.assertEqual([o.character_name for o in guest.opponents], ["trunks_future", "vegeta"])

    def test_an_unknown_fight_is_a_normal_match(self):
        import online
        from test_online_match import FakeNet, fake_game
        match = online.OnlineMatch(fake_game("goku"), FakeNet(), {"slot": 0, "epic": "no_such_fight",
                                                                  "opponent": {"character": "vegeta"}})
        self.assertEqual(match.player.character_name, "goku")
        self.assertEqual(match.opponent.character_name, "vegeta")

    def test_the_lobby_opens_epic_rooms(self):
        import online
        from test_online_match import FakeNet
        net = FakeNet()
        with patch.object(online.LobbyScreen, "connect"):
            lobby = online.LobbyScreen(net, (1200, 540), "trunks_future", epic=epic.by_id("goku_black"))
        lobby.create_room("1v1")
        self.assertEqual(net.sent[-1], {"t": "create", "mode": "team", "map": "capsule_corp", "epic": "goku_black"})
        label = online.LobbyScreen.room_label({"host": "Ann", "epic": "goku_black", "mode": "team"})
        self.assertIn("Black's Rosé", label)
        self.assertIn("you play Goku Black", label)


class EpicServerTests(unittest.TestCase):
    def test_a_room_keeps_its_fight(self):
        import importlib.util
        path = os.path.join(os.path.dirname(__file__), "..", "server", "lobby_server.py")
        spec = importlib.util.spec_from_file_location("lobby_server_epic", path)
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        room = server.Room(1, object(), "1v1", "cell_games", "cell_games")
        self.assertEqual((room.epic, room.mode), ("cell_games", "team"))
        self.assertIsNone(server.Room(2, object(), "1v1", "map", "bad id!").epic)
        self.assertEqual(server.PROTOCOL_VERSION, 4)


if __name__ == "__main__":
    unittest.main()
