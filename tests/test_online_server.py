import asyncio
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

    def client(self, name, character):
        client = NetClient()
        client.connect("127.0.0.1", self.server.port)
        wait_for(client, "welcome")
        client.send({"t": "hello", "name": name, "character": character})
        wait_for(client, "rooms")
        self.clients.append(client)
        return client

    def test_create_join_relay_and_leave(self):
        host = self.client("Alice", "goku")
        guest = self.client("Bob", "vegeta")

        host.send({"t": "create"})
        room = wait_for(host, "waiting")["room"]
        rooms = wait_for(guest, "rooms", where=lambda message: message["rooms"])["rooms"]
        self.assertEqual(rooms, [{"id": room, "host": "Alice", "character": "goku"}])

        guest.send({"t": "join", "room": room})
        host_start, guest_start = wait_for(host, "start"), wait_for(guest, "start")
        self.assertEqual((host_start["slot"], guest_start["slot"]), (0, 1))
        self.assertEqual(host_start["opponent"], {"name": "Bob", "character": "vegeta"})
        self.assertEqual(guest_start["opponent"], {"name": "Alice", "character": "goku"})

        # Match messages go to the other player only
        host.send({"t": "hit", "damage": 15, "source": [1, 2]})
        self.assertEqual(wait_for(guest, "hit"), {"t": "hit", "damage": 15, "source": [1, 2]})
        guest.send({"t": "state", "x": 5})
        self.assertEqual(wait_for(host, "state")["x"], 5)

        guest.send({"t": "leave"})
        wait_for(host, "opponent_left")

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
