import asyncio
import json
import os
import sys
import threading
import time
import unittest
import unittest.mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import lobby_server
from net import NetClient


class ServerThread:
    """A real lobby server on a free local port, in a background thread."""

    def __init__(self):
        self.port = None
        self._ready = threading.Event()
        self._loop = asyncio.new_event_loop()
        threading.Thread(target=self._run, daemon=True).start()
        self._ready.wait(5)

    def _run(self):
        asyncio.set_event_loop(self._loop)

        def ready(server):
            self.port = server.sockets[0].getsockname()[1]
            self._ready.set()

        try:
            self._loop.run_until_complete(lobby_server.serve("127.0.0.1", 0, ready))
        except asyncio.CancelledError:
            pass

    def stop(self):
        for task in asyncio.all_tasks(self._loop):
            self._loop.call_soon_threadsafe(task.cancel)


_pending = {}


def wait_for(client, kind, timeout=3, where=lambda message: True):
    """The next message of this kind that matches `where`; the other
    messages stay queued for later calls."""
    pending = _pending.setdefault(id(client), [])
    end = time.time() + timeout
    while time.time() < end:
        pending.extend(client.poll())
        for index, message in enumerate(pending):
            if message.get("t") == kind and where(message):
                del pending[: index + 1]
                return message
        time.sleep(0.01)
    raise AssertionError(f"no {kind!r} message")


class LobbyServerTests(unittest.TestCase):
    def setUp(self):
        self.server = ServerThread()
        self.clients = []

    def tearDown(self):
        for client in self.clients:
            client.close()
        self.server.stop()

    def client(self, name, character, allies=()):
        client = NetClient()
        client.connect("127.0.0.1", self.server.port)
        wait_for(client, "welcome")
        client.send({"t": "hello", "name": name, "character": character, "allies": list(allies),
                     "version": lobby_server.PROTOCOL_VERSION})
        wait_for(client, "rooms")
        self.clients.append(client)
        return client

    def test_create_join_relay_and_leave(self):
        host = self.client("Alice", "goku")
        guest = self.client("Bob", "vegeta")

        host.send({"t": "create"})
        room = wait_for(host, "waiting")["room"]
        rooms = wait_for(guest, "rooms", where=lambda message: message["rooms"])["rooms"]
        self.assertEqual(rooms, [{"id": room, "host": "Alice", "character": "goku", "mode": "1v1", "allies": [],
                                  "map": "map"}])

        guest.send({"t": "join", "room": room})
        host_start, guest_start = wait_for(host, "start"), wait_for(guest, "start")
        self.assertEqual((host_start["slot"], guest_start["slot"]), (0, 1))
        self.assertEqual(host_start["opponent"], {"name": "Bob", "character": "vegeta", "allies": []})
        self.assertEqual(host_start["mode"], "1v1")
        self.assertEqual(guest_start["opponent"], {"name": "Alice", "character": "goku", "allies": []})

        # Match messages go to the other player only
        host.send({"t": "hit", "damage": 15, "source": [1, 2]})
        self.assertEqual(wait_for(guest, "hit"), {"t": "hit", "damage": 15, "source": [1, 2]})
        guest.send({"t": "state", "x": 5})
        self.assertEqual(wait_for(host, "state")["x"], 5)

        guest.send({"t": "leave"})
        wait_for(host, "opponent_left")

    def test_an_epic_fight_online(self):
        """A host opens an Epic Fight's room; whoever joins plays the boss,
        whatever both had picked."""
        import pygame
        import epic
        import online
        from test_online_match import FakeNet, fake_game
        from utils.config import Config
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))
        fight = epic.by_id("cell_games")
        if fight is None or not epic.playable(fight):
            self.skipTest("characters not installed (setup.sh)")
        host = self.client("Alice", "gohan_teen")
        guest = self.client("Bob", "goku")
        host.send({"t": "create", "mode": "team", "map": fight.arena, "epic": fight.id})
        room = wait_for(host, "waiting")["room"]
        rooms = wait_for(guest, "rooms", where=lambda message: message["rooms"])["rooms"]
        self.assertEqual(rooms[0]["epic"], "cell_games")
        self.assertIn("you play Perfect Cell", online.LobbyScreen.room_label(rooms[0]))
        guest.send({"t": "join", "room": room})
        host_start, guest_start = wait_for(host, "start"), wait_for(guest, "start")
        self.assertEqual((host_start["epic"], guest_start["epic"]), ("cell_games", "cell_games"))
        self.assertEqual(host_start["mode"], "team")
        # Each game makes its side from the start message
        hero = online.OnlineMatch(fake_game("gohan_teen"), FakeNet(), host_start)
        boss = online.OnlineMatch(fake_game("goku"), FakeNet(), guest_start)
        self.assertEqual((hero.player.character_name, hero.player.form), ("gohan_teen", "ssj2"))
        self.assertEqual(hero.opponent.character_name, "cell_perfect")
        self.assertEqual(boss.player.character_name, "cell_perfect")
        self.assertEqual(boss.opponent.character_name, "gohan_teen")
        self.assertEqual((hero.arena, boss.arena), ("cell_games", "cell_games"))

    def test_a_disconnect_ends_the_match_and_full_rooms_are_hidden(self):
        host = self.client("Alice", "goku")
        guest = self.client("Bob", "gohan")
        watcher = self.client("Carl", "goku")
        host.send({"t": "create"})
        room = wait_for(host, "waiting")["room"]
        guest.send({"t": "join", "room": room})
        wait_for(host, "start")
        # The room is full: nobody else sees it or can join it
        watcher.send({"t": "list"})
        wait_for(watcher, "rooms", where=lambda message: message["rooms"] == [])
        watcher.send({"t": "join", "room": room})
        wait_for(watcher, "error")

        guest.close()
        wait_for(host, "opponent_left")

    def test_a_game_of_another_version_is_told_to_update_and_cannot_play(self):
        old = NetClient()
        old.connect("127.0.0.1", self.server.port)
        self.clients.append(old)
        self.assertEqual(wait_for(old, "welcome")["version"], lobby_server.PROTOCOL_VERSION)
        old.send({"t": "hello", "name": "Old", "character": "goku", "version": lobby_server.PROTOCOL_VERSION + 1})
        self.assertIn("update", wait_for(old, "error")["message"])
        old.send({"t": "create"})
        wait_for(old, "error")

    def test_the_game_and_the_server_speak_the_same_version(self):
        import net
        self.assertEqual(net.PROTOCOL_VERSION, lobby_server.PROTOCOL_VERSION)

    def test_the_server_says_its_version_which_is_the_games(self):
        import version
        self.assertEqual(lobby_server.SERVER_VERSION, version.__version__)
        client = NetClient()
        client.connect("127.0.0.1", self.server.port)
        self.clients.append(client)
        self.assertEqual(wait_for(client, "welcome")["server_version"], version.__version__)

    def test_a_flooding_client_gets_rate_limited(self):
        player = lobby_server.Player(1, writer=None)
        clock = [100.0]
        with unittest.mock.patch("lobby_server.time.monotonic", lambda: clock[0]):
            player.allowance_at = clock[0]
            taken = sum(player.take_message() for _ in range(1000))
            self.assertEqual(taken, lobby_server.MESSAGE_BURST)
            clock[0] += 1.0  # a second later: one second's worth again
            taken = sum(player.take_message() for _ in range(1000))
            self.assertEqual(taken, lobby_server.MESSAGES_PER_SECOND)
        self.assertEqual(player.dropped, 2000 - lobby_server.MESSAGE_BURST - lobby_server.MESSAGES_PER_SECOND)

    def start_match(self):
        host, guest = self.client("Alice", "goku"), self.client("Bob", "vegeta")
        host.send({"t": "create"})
        room = wait_for(host, "waiting")["room"]
        guest.send({"t": "join", "room": room})
        return host, wait_for(host, "start"), guest, wait_for(guest, "start")

    def wait_udp(self, *clients):
        end = time.time() + 3
        while not all(client.udp_ready for client in clients) and time.time() < end:
            for client in clients:
                client.send_state({"t": "state", "seq": 0})  # keeps knocking
            time.sleep(0.02)
        self.assertTrue(all(client.udp_ready for client in clients))

    def test_states_go_over_udp_and_the_rest_over_tcp(self):
        host, host_start, guest, guest_start = self.start_match()
        self.assertEqual(host_start["udp"]["port"], self.server.port)
        self.assertNotEqual(host_start["udp"]["token"], guest_start["udp"]["token"])
        host.start_udp(host_start["udp"]["token"], host_start["udp"]["port"])
        guest.start_udp(guest_start["udp"]["token"], guest_start["udp"]["port"])
        self.wait_udp(host, guest)

        # Once UDP works, a state no longer goes over TCP
        sent_over_tcp = []
        real_send = host.send
        host.send = lambda message: sent_over_tcp.append(message) or real_send(message)
        host.send_state({"t": "state", "seq": 7, "x": 1.5, "y": 2})
        state = wait_for(guest, "state", where=lambda message: message.get("seq") == 7)
        self.assertEqual((state["x"], state["y"]), (1.5, 2))
        self.assertNotIn("tok", state)  # the token stays between a player and the server
        self.assertEqual(sent_over_tcp, [])
        # Hits still go over TCP, which never loses one
        host.send({"t": "hit", "damage": 3})
        self.assertEqual(wait_for(guest, "hit")["damage"], 3)

    def test_without_udp_the_states_still_arrive_over_tcp(self):
        host, _, guest, _ = self.start_match()
        self.assertFalse(host.udp_ready)  # UDP never started (blocked, say)
        host.send_state({"t": "state", "seq": 3})
        wait_for(guest, "state", where=lambda message: message.get("seq") == 3)

    def test_udp_packets_of_strangers_are_ignored(self):
        host, host_start, guest, guest_start = self.start_match()
        guest.start_udp(guest_start["udp"]["token"], guest_start["udp"]["port"])
        self.wait_udp(guest)
        import socket as socket_module
        stranger = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)
        self.addCleanup(stranger.close)
        for token in ("not a token", None):
            stranger.sendto(json.dumps({"t": "state", "tok": token, "seq": 99}).encode(),
                            ("127.0.0.1", self.server.port))
        stranger.sendto(b"not json", ("127.0.0.1", self.server.port))
        host.send_state({"t": "state", "seq": 5})  # TCP: host has no UDP
        state = wait_for(guest, "state", where=lambda message: message.get("seq") in (5, 99))
        self.assertEqual(state["seq"], 5)

    def test_leaving_ends_the_tokens(self):
        host, host_start, guest, guest_start = self.start_match()
        guest.send({"t": "leave"})
        wait_for(host, "opponent_left")
        guest.start_udp(guest_start["udp"]["token"], guest_start["udp"]["port"])
        time.sleep(0.4)
        guest.send_state({"t": "state", "seq": 1})
        self.assertFalse(guest.udp_ready)

    def test_a_team_room_brings_each_players_allies(self):
        host = self.client("Alice", "goku", ["gohan", "trunks"])
        guest = self.client("Bob", "vegeta", ["broly"])
        host.send({"t": "create", "mode": "team"})
        room = wait_for(host, "waiting")["room"]
        rooms = wait_for(guest, "rooms", where=lambda message: message["rooms"])["rooms"]
        self.assertEqual(rooms[0]["mode"], "team")
        self.assertEqual(rooms[0]["allies"], ["gohan", "trunks"])
        guest.send({"t": "join", "room": room})
        host_start, guest_start = wait_for(host, "start"), wait_for(guest, "start")
        self.assertEqual((host_start["mode"], guest_start["mode"]), ("team", "team"))
        self.assertEqual(host_start["opponent"]["allies"], ["broly"])
        self.assertEqual(guest_start["opponent"]["allies"], ["gohan", "trunks"])

    def test_a_1v1_room_says_nothing_of_the_allies_and_bad_modes_are_1v1(self):
        host = self.client("Alice", "goku", ["gohan"])
        guest = self.client("Bob", "vegeta", ["broly"])
        host.send({"t": "create", "mode": "free for all"})
        room = wait_for(host, "waiting")["room"]
        guest.send({"t": "join", "room": room})
        start = wait_for(guest, "start")
        self.assertEqual((start["mode"], start["opponent"]["allies"]), ("1v1", []))

    def test_unreachable_server_reports_an_error(self):
        client = NetClient()
        client.connect("127.0.0.1", 1)
        end = time.time() + 5
        while client.status == "connecting" and time.time() < end:
            time.sleep(0.01)
        self.assertEqual(client.status, "error")
        self.assertIn("No server on 127.0.0.1:1", client.error)


if __name__ == "__main__":
    unittest.main()
