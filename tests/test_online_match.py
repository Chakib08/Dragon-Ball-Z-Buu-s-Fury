import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import online
from online import OnlineMatch, RemoteFighter
from saiyan import Saiyan
from utils.config import Config
from average_stats import use_average_stats


class FakeNet:
    """Two FakeNets wired together behave like the server relaying a match."""

    def __init__(self):
        self.status = "connected"
        self.sent = []
        self.peer = None
        self.inbox = []

    def send(self, message):
        self.sent.append(message)
        if self.peer is not None:
            self.peer.inbox.append(message)
        return True

    def poll(self):
        messages, self.inbox = self.inbox, []
        return messages


def fake_game(character):
    screen = pygame.display.get_surface()
    menu = SimpleNamespace(selected_character=character, character_names=("goku", "vegeta", "gohan"))
    return SimpleNamespace(screen=screen, resolution=screen.get_size(), menu=menu,
                           character=None, map_manager=None)


class OnlineMatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))

    def setUp(self):
        use_average_stats(self)
        self.net_a, self.net_b = FakeNet(), FakeNet()
        self.net_a.peer, self.net_b.peer = self.net_b, self.net_a
        self.game_a, self.game_b = fake_game("goku"), fake_game("vegeta")
        self.a = OnlineMatch(self.game_a, self.net_a,
                             {"slot": 0, "opponent": {"name": "Bob", "character": "vegeta"}})
        self.b = OnlineMatch(self.game_b, self.net_b,
                             {"slot": 1, "opponent": {"name": "Alice", "character": "goku"}})
        # What every game frame does: hitboxes follow the positions
        for match in (self.a, self.b):
            match.player.update()
            match.opponent.update()

    def exchange(self):
        """Both games send their state, then read what arrived."""
        for match in (self.a, self.b):
            match.last_sent_ms = -10_000
            match.after_frame()
        self.a.handle_messages(self.net_a.poll())
        self.b.handle_messages(self.net_b.poll())

    def test_players_start_apart_facing_each_other(self):
        self.assertEqual(self.a.player.facing, "Right")
        self.assertEqual(self.b.player.facing, "Left")
        self.assertEqual(self.a.opponent.position, self.b.player.position)
        self.assertEqual(self.game_a.map_manager.get_map().npcs, [])
        self.assertEqual(self.game_a.map_manager.get_map().portals, [])

    def test_snapshot_shows_the_same_frame_position_and_health(self):
        player = self.b.player
        player.move("Walk Left", 4)
        player.transform()
        while player.update_action():
            pass
        player.hp = 123
        player.start_block()
        self.exchange()
        remote = self.a.opponent
        for _ in range(20):
            remote.follow_snapshot()
        self.assertAlmostEqual(remote.position[0], player.position[0], places=1)
        self.assertEqual(remote.form, "ssj")
        self.assertEqual(remote.hp, 123)
        self.assertTrue(remote.blocking)
        self.assertEqual(remote.facing, player.facing)
        # Exactly the frame the other game shows
        name, flipped = player.animator.frame_key()
        self.assertIs(remote.image, remote.frame_image(name, flipped))

    def test_a_hit_on_the_opponent_is_applied_by_its_own_game(self):
        source = self.a.player.feet.center
        self.a.opponent.take_damage(20, source)
        self.assertEqual(self.net_a.sent[-1]["t"], "hit")
        hp = self.b.player.hp
        self.b.handle_messages(self.net_b.poll())
        # With the defender's own rules: online share, push, flinch
        self.assertAlmostEqual(hp - self.b.player.hp, 20 * OnlineMatch.DAMAGE_TAKEN)
        self.assertEqual(self.b.player.action["name"], "hurt")
        self.assertIsNotNone(self.b.player.knockback)

    def test_melee_from_the_combat_system_reaches_the_other_game(self):
        self.b.player.position = [self.a.player.position[0] + 15, self.a.player.position[1]]
        self.b.player.update()
        self.exchange()
        for _ in range(20):
            self.a.opponent.follow_snapshot()
        combat = self.game_a.map_manager.combat
        combat.last_player_attack_ms = -10_000
        with patch("combat.pygame.time.get_ticks", return_value=50_000):
            combat.update([], [], player_attacking=True, opponents=[self.a.opponent])
        self.assertTrue(combat.player_swung)
        hp = self.b.player.hp
        self.b.handle_messages(self.net_b.poll())
        self.assertLess(self.b.player.hp, hp)

    def test_techniques_are_shown_to_the_opponent_with_its_sprites_and_stop_on_them(self):
        combat_a = self.game_a.map_manager.combat
        combat_a.selected_technique = 1  # Kamehameha
        self.a.player.facing = "Right"
        combat_a._release(combat_a.technique, "Right")
        message = self.net_a.sent[-1]
        self.assertEqual((message["t"], message["id"], message["dir"]), ("tech", "kamehameha", "Right"))
        self.b.handle_messages(self.net_b.poll())
        combat_b = self.game_b.map_manager.combat
        self.assertEqual(len(combat_b.effects), 1)
        beam = combat_b.effects[0]
        self.assertTrue(beam.hits_player)
        hp = self.b.player.hp
        for _ in range(40):
            combat_b._update_effects()
        self.assertTrue(beam.hit)  # stopped on B's fighter
        # Only A's "hit" message does damage
        self.assertEqual(self.b.player.hp, hp)

    def test_the_opponent_sees_a_charged_technique_at_the_same_size(self):
        heights = []
        for power in (0.0, 1.0):
            combat_a = self.game_a.map_manager.combat
            combat_a.selected_technique = 1
            combat_a._release(combat_a.technique, "Right", power)
            message = self.net_a.sent[-1]
            self.assertEqual(message["power"], power)
            combat_b = self.game_b.map_manager.combat
            combat_b.effects.clear()
            self.b.handle_messages(self.net_b.poll())
            heights.append(combat_b.effects[-1].pieces["heads"][0].get_height())
        self.assertLess(heights[0], heights[1])

    def test_knock_out_ends_the_match_on_both_sides(self):
        self.b.player.hp = 0
        self.b.after_frame()
        self.assertEqual(self.b.result, "lose")
        self.a.handle_messages(self.net_a.poll())
        self.assertEqual(self.a.result, "win")
        self.assertEqual(self.a.opponent.hp, 0)
        with patch("online.pygame.time.get_ticks", return_value=self.a.result_since + OnlineMatch.RESULT_MS):
            self.assertTrue(self.a.finished)

    def test_opponent_leaving_or_connection_loss_ends_the_match(self):
        self.a.handle_messages([{"t": "opponent_left"}])
        self.assertEqual(self.a.result, "left")
        self.net_b.status = "error"
        self.b.handle_messages([])
        self.assertEqual(self.b.result, "disconnected")

    def test_bad_messages_are_ignored(self):
        self.a.handle_messages([
            {"t": "hit", "damage": "lots"},
            {"t": "beam", "origin": None},
            {"t": "state", "x": "?"},
            {"t": "state", "x": 1, "y": 2, "frame": ["No such frame", False], "form": "ssj4"},
        ])
        self.assertEqual(self.a.player.hp, self.a.player.max_hp)


class AddressTests(unittest.TestCase):
    def test_server_addresses(self):
        parse = online.user_settings.parse_address
        self.assertEqual(parse("192.168.1.20:5050"), ("192.168.1.20", 5050))
        self.assertEqual(parse("example.org"), ("example.org", 5050))
        self.assertIsNone(parse("host:99999"))
        self.assertIsNone(parse(":5050"))
        self.assertIsNone(parse(""))


if __name__ == "__main__":
    unittest.main()
