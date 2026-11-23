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
        # The Z Fighters against a crowd of Cell Juniors
        self.assertTrue(all(name == "cell_jr" for wave in juniors.waves for name in wave))
        self.assertGreaterEqual(sum(len(wave) for wave in juniors.waves), 7)
        self.assertTrue({"piccolo", "tien", "yamcha", "krillin"} <= set(juniors.allies))
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
        allies = {npc.character_name: npc.form for npc in game.map_manager.get_map().npcs if npc.team == HEROES}
        fight = epic.by_id("goku_black")
        self.assertEqual(allies, {name: fight.ally_forms.get(name, "base") for name in fight.allies})
        self.assertEqual(allies["vegito"], "ssjb")  # Vegito Blue

    def test_the_cell_juniors_fight_has_everyone(self):
        fight = epic.by_id("cell_juniors")
        game = self.game("cell_juniors")
        npcs = game.map_manager.get_map().npcs
        self.assertEqual((game.character.character_name, game.character.form), (fight.hero, fight.form or "base"))
        allies = {npc.character_name: npc.form for npc in npcs if npc.team == HEROES}
        self.assertEqual(allies, {name: fight.ally_forms.get(name, "base") for name in fight.allies})
        self.assertEqual([npc.character_name for npc in self.enemies(game)], fight.waves[0])
        # The allies stand around the player, not in each other
        bodies = [game.character.body, *(npc.body for npc in npcs if npc.team == HEROES)]
        overlapping = sum(1 for i, a in enumerate(bodies) for b in bodies[i + 1:] if a.colliderect(b))
        self.assertLessEqual(overlapping, 2)
        for _ in range(60):
            game.loop_once([])

    def test_enemies_are_stronger_and_allies_weaker_in_an_epic_fight(self):
        from npc import SaiyanNPC
        game = self.game("cell_juniors")
        npcs = game.map_manager.get_map().npcs
        junior = next(npc for npc in npcs if npc.team != HEROES)
        plain = SaiyanNPC(0, 0, False, "cell_jr", 0, [], difficulty=junior.difficulty.name)
        self.assertEqual(junior.max_hp, round(plain.max_hp * epic.ENEMY_STRENGTH))
        self.assertEqual(junior.hp, junior.max_hp)
        self.assertAlmostEqual(junior.attack_damage, plain.attack_damage * epic.ENEMY_STRENGTH)
        self.assertAlmostEqual(junior.technique_damage, plain.technique_damage * epic.ENEMY_STRENGTH)
        ally = next(npc for npc in npcs if npc.team == HEROES)
        normal = SaiyanNPC(0, 0, False, ally.character_name, 0, [], team=HEROES)
        self.assertAlmostEqual(ally.attack_damage, normal.attack_damage * epic.ALLY_STRENGTH)
        self.assertEqual(ally.max_hp, normal.max_hp)  # as healthy, but hitting softer
        # A later wave is as strong
        android = self.game("android13")
        android.scenes["story"].intro = None
        self.beat(self.enemies(android))
        android.loop_once([])
        thirteen = next(npc for npc in self.enemies(android) if npc.hp > 0)
        plain13 = SaiyanNPC(0, 0, False, "android13", 0, [], difficulty=thirteen.difficulty.name)
        self.assertEqual(thirteen.max_hp, round(plain13.max_hp * epic.ENEMY_STRENGTH))
        # Arcade fights are not changed
        from game import Game
        arcade = Game((1200, 540), "test", fullscreen=False)
        arcade.menu = Menu(arcade.resolution)
        arcade.start_story()
        gohan = self.enemies(arcade)[0]
        self.assertEqual(gohan.max_hp, SaiyanNPC(0, 0, False, "gohan", 0, [], difficulty=gohan.difficulty.name).max_hp)

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
        game.menu.selected_enemies = ["cell_jr"] * 10
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

    def test_winning_the_last_fight_shows_the_victory_animation(self):
        from epic_screens import VictoryAnimation
        if not VictoryAnimation.frames():
            self.skipTest("Graphics/victory_frames.png missing")
        for fight in epic.fights()[:-1]:
            epic.mark_cleared(fight)
        last = epic.fights()[-1]
        game = self.game(last.id)
        story = game.scenes["story"]
        story.intro = None
        self.beat(self.enemies(game))
        game.loop_once([])
        self.assertIsNotNone(story.celebration)
        self.assertEqual(len(VictoryAnimation.frames()), 24)
        self.assertIsNotNone(story.celebration.animation.frame(400))
        # A key goes on to the result
        story.celebration.shown_at -= 10_000
        game.loop_once([key(pygame.K_RETURN)])
        self.assertIsNone(story.celebration)
        self.assertTrue(story.result.victory)
        # Winning it again: no second celebration
        game.loop_once([key(pygame.K_RETURN)])
        story.intro = None
        self.beat(self.enemies(game))
        game.loop_once([])
        self.assertIsNone(story.celebration)
        # The Epic Fights list shows it by its title
        menu = Menu((1200, 540))
        menu.state = State.EPIC_SELECT
        menu.launch_menu(pygame.Surface((1200, 540)), (1200, 540), [])
        self.assertIsNotNone(menu.victory_animation)

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
        fight = epic.by_id("goku_black")
        self.assertEqual([a.character_name for a in host.allies], fight.allies[:epic.ONLINE_ALLIES])
        self.assertEqual(host.opponent.character_name, "goku_black")
        self.assertEqual(host.arena, "capsule_corp")
        guest = online.OnlineMatch(fake_game("vegeta"), net_b, {"slot": 1, "mode": "team", "epic": "goku_black",
                                                                "opponent": {"character": "goku"}})
        self.assertEqual(guest.player.character_name, "goku_black")
        self.assertEqual(guest.player.form, "ssj")  # Rosé
        self.assertEqual(guest.opponent.character_name, "trunks_future")
        self.assertEqual([o.character_name for o in guest.opponents],
                         ["trunks_future", *fight.allies[:epic.ONLINE_ALLIES]])

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


class QuestTests(EpicCase):
    def game(self, fight_id):
        from game import Game
        game = Game((1200, 540), "test", fullscreen=False)
        game.menu = Menu(game.resolution)
        game.menu.epic = epic.by_id(fight_id)
        game.start_story()
        game.scenes["story"].intro = None
        return game

    def test_surviving_sixty_seconds_wins_the_last_hope(self):
        fight = epic.by_id("last_hope")
        self.assertEqual((fight.hero, fight.allies, fight.waves), ("trunks_teen", ["gohan_future"],
                                                                   [["android17", "android18"]]))
        self.assertEqual(fight.arena, "pepper_town")
        self.assertGreater(fight.quest.survive, 0)
        game = self.game("last_hope")
        story = game.scenes["story"]
        self.assertIsNotNone(story.quest_panel)
        for _ in range(30):
            game.loop_once([])
        self.assertIsNone(story.result)
        self.assertGreater(game.quest_elapsed_ms, 0)
        game.character.hp = game.character.max_hp  # held out...
        game.quest_elapsed_ms = fight.quest.survive * 1000
        game.loop_once([])
        self.assertIsNotNone(story.result)
        self.assertTrue(story.result.victory)

    def test_the_timer_stands_still_on_the_versus_card(self):
        game = self.game("last_hope")
        game.scenes["story"].begin(epic.by_id("last_hope"))  # the card again
        for _ in range(20):
            game.loop_once([])
        self.assertEqual(game.quest_elapsed_ms, 0)

    def test_kid_buu_falls_to_the_spirit_bomb_only(self):
        fight = epic.by_id("kid_buu")
        self.assertEqual(fight.quest.protect, ["vegeta"])
        self.assertEqual(fight.quest.finisher, "spirit_bomb")
        game = self.game("kid_buu")
        combat = game.map_manager.combat
        buu = next(npc for npc in game.map_manager.get_map().npcs if npc.team != HEROES)
        self.assertEqual(buu.finisher, "spirit_bomb")
        buu.take_damage(100_000)  # a punch
        self.assertEqual(buu.hp, 1)
        combat._hit_target(buu, 100_000, buu.feet.center, 1.0, "kamehameha")
        self.assertEqual(buu.hp, 1)
        self.assertIsNone(game.story_outcome())
        combat._hit_target(buu, 100_000, buu.feet.center, 1.0, "spirit_bomb")
        self.assertEqual(buu.hp, 0)
        # Goku has it, as a Super Saiyan 3 too
        self.assertEqual(game.character.form, "ssj3")
        self.assertIn("spirit_bomb", [t.id for t in game.character.techniques])
        self.assertTrue(game.character.has_animation("Tech spirit_bomb Right 0"))

    def test_vegeta_falling_loses_the_kid_buu_fight(self):
        game = self.game("kid_buu")
        vegeta = next(npc for npc in game.map_manager.get_map().npcs if npc.character_name == "vegeta")
        vegeta.take_damage(100_000)
        self.assertEqual(game.story_outcome(), "defeat")

    def test_the_quest_in_words(self):
        from epic_screens import quest_lines
        self.assertEqual(quest_lines(epic.by_id("kid_buu")),
                         ["Vegeta must survive", "Finish Kid Buu with the Spirit Bomb"])
        seconds = int(epic.by_id("last_hope").quest.survive)
        self.assertEqual(quest_lines(epic.by_id("last_hope")), [f"Survive for {seconds} seconds"])
        self.assertEqual(quest_lines(epic.by_id("namek")), ["Defeat every enemy"])
