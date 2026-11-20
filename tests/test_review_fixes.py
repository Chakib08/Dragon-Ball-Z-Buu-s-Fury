"""Fixes from a review of the whole code: effects across maps, the beam's
redrawing, reconnecting, numbers from the network, the dialog box, touch
copies and the app going to the background, the server's memory, and the
speed of the chase path search."""

import os
import socket
import sys
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server"))

import effects
import lobby_server
from dialog.dialogbox import DialogBox
from map import MapManager
from net import NetClient
from online import RemoteFighter, _number
from saiyan import Saiyan
from touch_controls import TouchControls
from utils.config import Config


class EffectsAcrossMapsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def setUp(self):
        patcher = patch("pygame.time.get_ticks", return_value=10_000)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.screen = pygame.display.set_mode((1200, 540))
        self.player = Saiyan(159, 289, False, "goku")
        self.manager = MapManager(self.screen, self.player)

    def fire(self):
        blast = next(t for t in self.player.techniques if t.kind == "projectile")
        effect = self.manager.combat._release_by(self.player, blast, "Right")
        self.manager.update()  # puts it in the map's sprite group
        return effect

    def test_going_through_a_door_ends_the_flying_effects(self):
        world = self.manager.get_map()
        effect = self.fire()
        self.assertIn(effect, world.group)
        self.manager.transitioning = True
        self.manager.transitioning_in = True
        self.manager.new_map, self.manager.new_position = "house", "spawn_house"
        self.manager.transition_alpha = 255
        self.manager.black_transition()
        self.assertTrue(effect.done)
        self.assertEqual(self.manager.combat.effects, [])
        self.manager.update()  # in the house now
        self.assertNotIn(effect, world.group)  # not left drawn on the world map

    def test_finished_effects_leave_the_group(self):
        effect = self.fire()
        effect.done = True
        self.manager.update()
        self.assertNotIn(effect, self.manager.get_map().group)


class BeamDrawingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def beam(self, hold_ticks=40):
        piece = pygame.Surface((8, 6))
        pieces = {"start": piece, "bodies": [piece], "heads": [piece, piece], "impacts": None}
        self.drawn = 0

        def orient(image, direction):
            self.drawn += 1
            return image

        return effects.Beam(pieces, (0, 0), "Right", 9, 90, 10, None, hold_ticks, orient)

    def test_a_held_beam_is_only_redrawn_when_its_head_animates(self):
        beam = self.beam()
        while not beam.stopped:
            beam.update_effect([])
        self.drawn = 0
        for _ in range(40):
            beam.update_effect([])
        # One redraw per head frame (every FRAME_TICKS), not one or two a tick
        self.assertLessEqual(self.drawn, 40 // effects.Beam.FRAME_TICKS + 1)

    def test_a_growing_beam_is_drawn_once_per_tick(self):
        beam = self.beam()
        self.drawn = 0
        for _ in range(5):
            beam.update_effect([])
        self.assertEqual(self.drawn, 5)
        self.assertGreater(beam.rect.width, 40)  # it did grow


class ReconnectTests(unittest.TestCase):
    """A thread of a closed connection must not touch the new one."""

    def listening_socket(self):
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen()
        self.addCleanup(server.close)
        return server

    def wait(self, condition, seconds=3):
        end = time.time() + seconds
        while time.time() < end:
            if condition():
                return True
            time.sleep(0.01)
        return False

    def test_reconnecting_keeps_the_new_connection(self):
        first, second = self.listening_socket(), self.listening_socket()
        accepted = []
        for server in (first, second):
            threading.Thread(target=lambda s=server: accepted.append(s.accept()[0]), daemon=True).start()
        self.addCleanup(lambda: [conn.close() for conn in accepted])

        net = NetClient()
        self.addCleanup(net.close)
        net.connect(*first.getsockname())
        self.assertTrue(self.wait(lambda: net.connected))
        net.connect(*second.getsockname())  # closes the first one
        self.assertTrue(self.wait(lambda: net.connected))
        time.sleep(0.3)  # the first connection's thread has ended by now
        self.assertTrue(net.connected, net.error)
        self.assertEqual(net.error, "")

    def test_messages_of_the_old_connection_are_dropped(self):
        net = NetClient()
        net._inbox.put({"t": "start"})
        with patch.object(threading.Thread, "start"):  # no real connection
            net.connect("127.0.0.1", 1)
        self.assertEqual(net.poll(), [])


class NetworkNumbersTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def test_only_finite_numbers_are_taken(self):
        self.assertEqual(_number("3.5"), 3.5)
        for bad in (float("nan"), float("inf"), "-inf", None, "x", [1]):
            self.assertIsNone(_number(bad))

    def test_a_snapshot_with_nan_or_infinity_cannot_break_the_opponent(self):
        opponent = RemoteFighter("goku", "Bob", lambda message: None)
        opponent.place(100, 100, "Left")
        opponent.apply_snapshot({"x": float("nan"), "y": 5, "facing": "Right"})
        self.assertEqual(opponent.position, [100, 100])  # ignored
        opponent.apply_snapshot({"x": 110, "y": 100, "hp": float("nan"), "max_hp": float("inf"), "ki": "x"})
        self.assertEqual(opponent.target_position, [110.0, 100.0])
        self.assertTrue(0 <= opponent.hp <= opponent.max_hp < float("inf"))
        # The health bar can be drawn
        fraction = max(0, min(1, opponent.hp / opponent.max_hp))
        round(120 * fraction)


class DialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def test_nothing_to_say_keeps_the_box_closed(self):
        box = DialogBox((1200, 540))
        box.open(())
        self.assertFalse(box.isBoxOpened)
        box.render(pygame.Surface((1200, 540)))  # no IndexError
        box.open(["Hi!"])
        self.assertTrue(box.isBoxOpened)
        box.render(pygame.Surface((1200, 540)))


class TouchControlsAndroidTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def test_the_mouse_copy_of_a_touch_is_ignored(self):
        controls = TouchControls((1200, 540))
        x, y = controls.buttons["attack"]
        controls.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(int(x), int(y)), touch=True))
        self.assertFalse(controls.consume_action("attack"))
        controls.handle_event(pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / 1200, y=y / 540))
        self.assertTrue(controls.consume_action("attack"))

    def test_going_to_the_background_lets_go_of_everything(self):
        controls = TouchControls((1200, 540))
        x, y = controls.buttons["block"]
        controls.handle_event(pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / 1200, y=y / 540))
        self.assertTrue(controls.blocking)
        for name in ("APP_WILLENTERBACKGROUND", "WINDOWFOCUSLOST"):
            if hasattr(pygame, name):
                with self.subTest(event=name):
                    controls.handle_event(pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / 1200, y=y / 540))
                    controls.handle_event(pygame.event.Event(getattr(pygame, name)))
                    self.assertFalse(controls.blocking)


class ServerMemoryTests(unittest.TestCase):
    def test_a_client_that_stops_reading_is_dropped(self):
        written = []
        transport = SimpleNamespace(get_write_buffer_size=lambda: 0)
        writer = SimpleNamespace(is_closing=lambda: False, write=written.append, transport=transport,
                                 close=lambda: setattr(writer, "closed", True), closed=False)
        player = lobby_server.Player(1, writer)
        player.send({"t": "state"})
        self.assertEqual(len(written), 1)
        transport.get_write_buffer_size = lambda: lobby_server.MAX_PENDING_BYTES + 1
        player.send({"t": "state"})
        self.assertEqual(len(written), 1)  # not queued any more
        self.assertTrue(writer.closed)


class PathSearchSpeedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def test_a_long_search_on_the_world_map_does_not_stall_the_game(self):
        with patch("pygame.time.get_ticks", return_value=10_000):
            player = Saiyan(159, 289, False, "goku")
            manager = MapManager(pygame.display.set_mode((1200, 540)), player, enemies=("gohan",))
            enemy = manager.get_map().npcs[0]
            enemy.target = player
            start = time.perf_counter()
            # Across the river: a big search
            manager.combat.ai.find_path(enemy, (430, 300), manager.get_collisions())
        self.assertLess(time.perf_counter() - start, 0.05)


if __name__ == "__main__":
    unittest.main()
