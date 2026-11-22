"""Game controller support (the ROG Ally's controls, Xbox, PlayStation...),
with a simulated controller: there is none on the test machine."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import gamepad as gamepad_module
from game import Game
from gamepad import AXIS_MAX, BUTTONS, Gamepad
from menu import Menu, State
from utils.config import Config

from average_stats import steady_module_fixtures

# Repeatable NPCs: no lucky dodges or blocks (see average_stats.py)
setUpModule, tearDownModule = steady_module_fixtures()



class FakeController:
    """Stands for pygame._sdl2.controller.Controller."""

    def __init__(self):
        self.buttons = set()
        self.axes = {}

    def press(self, *names):
        self.buttons |= {getattr(pygame, BUTTONS[name]) for name in names}

    def release(self, *names):
        self.buttons -= {getattr(pygame, BUTTONS[name]) for name in names}

    def get_button(self, button):
        return button in self.buttons

    def get_axis(self, axis):
        return self.axes.get(axis, 0)

    def stick(self, x, y):
        self.axes[pygame.CONTROLLER_AXIS_LEFTX] = int(x * AXIS_MAX)
        self.axes[pygame.CONTROLLER_AXIS_LEFTY] = int(y * AXIS_MAX)

    def trigger(self, name, value):
        axis = pygame.CONTROLLER_AXIS_TRIGGERLEFT if name == "lt" else pygame.CONTROLLER_AXIS_TRIGGERRIGHT
        self.axes[axis] = int(value * AXIS_MAX)


class FakeControllerModule:
    def __init__(self, pads):
        self.pads = pads

    def init(self):
        pass

    def get_count(self):
        return len(self.pads)

    def is_controller(self, index):
        return True

    def Controller(self, index):
        return self.pads[index]


def plug(test, *pads):
    patcher = patch.object(gamepad_module, "sdl_controller", FakeControllerModule(list(pads)))
    patcher.start()
    test.addCleanup(patcher.stop)


class GamepadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    def setUp(self):
        self.pad = FakeController()
        plug(self, self.pad)
        self.gamepad = Gamepad()

    def test_a_press_counts_once_while_held(self):
        self.assertTrue(self.gamepad.connected)
        self.pad.press("a")
        self.gamepad.update(0)
        self.assertEqual(self.gamepad.pressed, {"a"})
        self.gamepad.update(17)
        self.assertEqual(self.gamepad.pressed, set())
        self.assertIn("a", self.gamepad.held)
        self.pad.release("a")
        self.gamepad.update(34)
        self.assertNotIn("a", self.gamepad.held)

    def test_the_stick_ignores_small_moves_and_runs_at_the_edge(self):
        self.pad.stick(0.1, 0.1)
        self.gamepad.update(0)
        self.assertEqual(self.gamepad.move_vector, (0.0, 0.0))
        self.pad.stick(0.5, 0)
        self.gamepad.update(17)
        self.assertAlmostEqual(self.gamepad.move_vector[0], 0.5, places=3)
        self.assertFalse(self.gamepad.running)
        self.pad.stick(1, 0)
        self.gamepad.update(34)
        self.assertTrue(self.gamepad.running)

    def test_the_d_pad_moves_and_the_left_trigger_runs(self):
        self.pad.press("up", "left")
        self.pad.trigger("lt", 1.0)
        self.gamepad.update(0)
        self.assertEqual(self.gamepad.move_vector, (-1.0, -1.0))
        self.assertTrue(self.gamepad.running)
        self.pad.trigger("lt", 0.2)  # barely pressed: not yet
        self.gamepad.update(17)
        self.assertNotIn("lt", self.gamepad.held)

    def test_in_menus_the_stick_steps_like_the_d_pad_and_repeats(self):
        self.pad.stick(0, 1)
        self.gamepad.update(0)
        self.assertEqual(self.gamepad.menu_presses(), {"down"})
        self.gamepad.update(100)
        self.assertEqual(self.gamepad.menu_presses(), set())  # not again right away
        self.gamepad.update(Gamepad.REPEAT_DELAY_MS + 10)
        self.assertEqual(self.gamepad.menu_presses(), {"down"})  # held: repeats
        self.pad.stick(0, 0)
        self.gamepad.update(1000)
        self.pad.stick(0, -1)
        self.gamepad.update(1017)
        self.assertEqual(self.gamepad.menu_presses(), {"up"})

    def test_plugging_and_unplugging(self):
        module = gamepad_module.sdl_controller
        module.pads.clear()
        self.gamepad.handle_event(pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=0))
        self.assertFalse(self.gamepad.connected)
        module.pads.append(self.pad)
        self.gamepad.handle_event(pygame.event.Event(pygame.CONTROLLERDEVICEADDED, device_index=0))
        self.assertTrue(self.gamepad.connected)

    def test_touching_the_screen_leaves_controller_mode(self):
        self.pad.press("a")
        self.gamepad.update(0)
        self.assertTrue(self.gamepad.active)
        self.gamepad.handle_event(pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=0.5, y=0.5))
        self.assertFalse(self.gamepad.active)

    def test_no_controller_module_means_no_controller(self):
        with patch.object(gamepad_module, "sdl_controller", None):
            pad = Gamepad()
            pad.update(0)
        self.assertFalse(pad.connected)
        self.assertEqual(pad.move_vector, (0.0, 0.0))


class GamepadInGameTests(unittest.TestCase):
    """The real main loop (Game.loop_once), driven by the controller."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    def setUp(self):
        self.now = 10_000
        patcher = patch("pygame.time.get_ticks", side_effect=lambda: self.now)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.pad = FakeController()
        plug(self, self.pad)
        self.game = Game((1200, 540), "test", fullscreen=False)
        self.game.menu = Menu((1200, 540))

    def frames(self, count=1, events=()):
        for _ in range(count):
            self.now += 17
            self.game.loop_once(list(events))
            events = ()

    def tap(self, *names):
        """Press and release buttons (one frame each)."""
        self.pad.press(*names)
        self.frames()
        self.pad.release(*names)
        self.frames()

    def start_fight(self):
        self.game.menu.state = State.START
        self.game.menu.selected_item = [item for item, _, _ in Menu.MAIN_ITEMS].index("arcade")
        self.tap("a")                     # Arcade -> character
        self.tap("a")                     # Goku -> allies
        self.tap("a")                     # (none) -> opponents
        self.tap("a")                     # Gohan -> arena
        self.tap("a")                     # Goku's home -> fight
        self.assertEqual(self.game.scene, "story")
        npc = self.game.map_manager.get_map().npcs[0]
        npc.attack_damage = 0
        npc.next_technique_ms = float("inf")

    def test_the_whole_menu_works_with_the_controller(self):
        menu = self.game.menu
        self.tap("down")
        self.assertEqual(Menu.MAIN_ITEMS[menu.selected_item][0], "online")
        self.tap("up")
        self.tap("a")
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        self.tap("right")
        self.assertEqual(menu.selected_character, "vegeta")
        self.tap("b")
        self.assertEqual(menu.state, State.START)  # B goes back
        self.tap("a")
        self.tap("a")                              # Vegeta
        self.assertEqual(menu.state, State.ALLY_SELECT)
        self.tap("right")
        self.tap("x")                              # X picks a card
        self.assertEqual(menu.selected_allies, ["gohan"])
        self.tap("a")
        self.assertEqual(menu.state, State.ENEMY_SELECT)
        self.tap("a")
        self.assertEqual(menu.state, State.MAP_SELECT)
        self.tap("right")                          # the next arena
        self.assertNotEqual(menu.selected_arena, "map")
        self.tap("b")
        self.assertEqual(menu.state, State.ENEMY_SELECT)  # B goes back
        self.tap("a")
        self.tap("a")
        self.assertEqual(self.game.scene, "story")

    def test_fighting_with_the_controller(self):
        self.start_fight()
        player = self.game.character
        # Left stick: walk
        start = list(player.position)
        self.pad.stick(1, 0)
        self.frames(10)
        self.pad.stick(0, 0)
        self.frames()
        self.assertGreater(player.position[0], start[0])
        # A: one punch or kick
        self.pad.press("a")
        self.frames()
        self.assertTrue(self.game.map_manager.combat.player_swung or player.action is not None)
        self.pad.release("a")
        self.frames(30)
        # B held: guard
        self.pad.press("b")
        self.frames(3)
        self.assertTrue(player.blocking)
        self.pad.release("b")
        self.frames(3)
        self.assertFalse(player.blocking)
        # Y: transform
        player.ki = player.max_ki
        self.tap("y")
        self.assertEqual(player.action and player.action["name"], "transform")
        while player.action is not None:
            self.frames()
        self.assertTrue(player.is_super)

    def test_holding_x_charges_and_releasing_fires(self):
        self.start_fight()
        combat = self.game.map_manager.combat
        player = self.game.character
        combat.selected_technique = next(i for i, t in enumerate(player.techniques) if t.kind == "beam")
        player.ki = player.max_ki
        self.pad.press("x")
        self.frames(20)
        self.assertTrue(combat.charging)
        self.pad.release("x")
        self.frames()
        self.assertFalse(combat.charging)
        self.assertEqual(player.action["name"], "special")

    def test_shoulders_change_the_technique(self):
        self.start_fight()
        combat = self.game.map_manager.combat
        first = combat.selected_technique
        self.tap("rb")
        self.assertEqual(combat.selected_technique, (first + 1) % len(combat.techniques))
        self.tap("lb")
        self.assertEqual(combat.selected_technique, first)

    def test_the_menu_button_pauses_and_a_never_quits(self):
        self.start_fight()
        self.tap("menu")
        self.assertTrue(self.game.quit_prompt.is_open)
        self.tap("a")                          # by habit: does not quit
        self.assertTrue(self.game.isRunning)
        self.tap("b")                          # B: back to the fight
        self.assertFalse(self.game.quit_prompt.is_open)
        self.tap("menu")
        self.tap("y")                          # Y: main menu
        self.assertEqual(self.game.scene, "menu")
        self.assertTrue(self.game.isRunning)
        self.game.menu.state = State.START
        self.tap("b")                          # B on the main menu: quit question
        self.assertTrue(self.game.quit_prompt.is_open)
        self.tap("x")                          # X: quit
        self.assertFalse(self.game.isRunning)

    def test_retry_with_the_controller(self):
        self.start_fight()
        self.game.character.hp = 0
        self.frames(60)
        self.assertIsNotNone(self.game.result)
        old = self.game.character
        self.tap("a")
        self.assertIsNot(self.game.character, old)
        self.assertEqual(self.game.scene, "story")

    def test_controller_hints_replace_the_touch_buttons(self):
        self.start_fight()
        self.tap("a")
        self.assertTrue(self.game.touch_controls.hidden)
        self.assertTrue(self.game.quit_prompt.gamepad_hints)
        self.frames(1, [pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=0.5, y=0.5)])
        self.frames()
        self.assertFalse(self.game.touch_controls.hidden)


if __name__ == "__main__":
    unittest.main()
