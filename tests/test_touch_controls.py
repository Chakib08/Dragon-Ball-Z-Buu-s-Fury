import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from menu import Menu, State
from touch_controls import TouchControls
from utils.config import Config


class TouchControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.controls = TouchControls((1200, 1000))

    def finger_event(self, event_type, finger_id, control):
        x, y = self.controls.buttons[control]
        return pygame.event.Event(
            event_type,
            finger_id=finger_id,
            x=x / 1200,
            y=y / 1000,
        )

    def test_multiple_fingers_hold_directions_until_each_is_released(self):
        self.controls.handle_event(self.finger_event(pygame.FINGERDOWN, 1, "up"))
        self.controls.handle_event(self.finger_event(pygame.FINGERDOWN, 2, "right"))

        self.assertEqual(self.controls.directions, {"up", "right"})

        self.controls.handle_event(self.finger_event(pygame.FINGERUP, 1, "up"))
        self.assertEqual(self.controls.directions, {"right"})

    def test_action_buttons_fire_once_and_release(self):
        self.controls.handle_event(self.finger_event(pygame.FINGERDOWN, 7, "attack"))

        self.assertTrue(self.controls.attacking)
        self.assertTrue(self.controls.consume_action("attack"))
        self.assertFalse(self.controls.consume_action("attack"))

        self.controls.handle_event(self.finger_event(pygame.FINGERUP, 7, "attack"))
        self.assertFalse(self.controls.attacking)
        self.assertNotIn("attack", self.controls.pointers.values())

    def test_super_and_special_buttons_fire_once_per_press_and_do_not_overlap(self):
        for control in ("super", "special"):
            with self.subTest(control=control):
                self.controls.handle_event(self.finger_event(pygame.FINGERDOWN, 3, control))
                self.assertTrue(self.controls.consume_action(control))
                self.assertFalse(self.controls.consume_action(control))
                self.controls.handle_event(self.finger_event(pygame.FINGERUP, 3, control))
        # Each button centre resolves to its own button
        for control, center in self.controls.buttons.items():
            self.assertEqual(self.controls._control_at(center), control)

    def test_buttons_stay_on_screen_and_apart_on_phone_and_desktop_sizes(self):
        for size in ((1200, 1000), (2400, 1080), (1280, 720), (1920, 1080), (3200, 1440)):
            with self.subTest(size=size):
                controls = TouchControls(size)
                radius = controls.button_size * 0.63
                for control, (x, y) in controls.buttons.items():
                    self.assertTrue(radius <= x <= size[0] - radius * 0.9, control)
                    self.assertTrue(radius <= y <= size[1] - radius * 0.5, control)
                    self.assertEqual(controls._control_at((x, y)), control)
        self.assertGreater(TouchControls((3200, 1440)).button_size, TouchControls((1200, 1000)).button_size)

    def test_controls_render_on_screen(self):
        screen = pygame.Surface((1200, 1000))
        self.controls.draw(screen)
        center = tuple(round(value) for value in self.controls.buttons["attack"])
        self.assertNotEqual(screen.get_at(center)[:3], (0, 0, 0))

    def test_mouse_actions_work_and_focus_loss_clears_all_state(self):
        x, y = self.controls.buttons["interact"]
        self.controls.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=(round(x), round(y)),
            )
        )
        self.assertTrue(self.controls.consume_action("interact"))
        self.controls.handle_event(
            pygame.event.Event(pygame.WINDOWFOCUSLOST)
        )

        self.assertEqual(self.controls.pointers, {})
        self.assertFalse(self.controls.consume_action("interact"))

    def test_character_selection_and_options_can_be_opened_by_touch(self):
        resolution = (1200, 1000)
        screen = pygame.Surface(resolution)
        menu = Menu(resolution)
        start_center = (resolution[0] - 520, resolution[1] / 1.5)
        menu.launch_menu(
            screen,
            resolution,
            [
                pygame.event.Event(
                    pygame.FINGERDOWN,
                    finger_id=3,
                    x=start_center[0] / resolution[0],
                    y=start_center[1] / resolution[1],
                )
            ],
        )
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        menu.launch_menu(screen, resolution, [])
        goten_rect = menu.character_rects["goten"]
        menu.launch_menu(
            screen,
            resolution,
            [
                pygame.event.Event(
                    pygame.FINGERDOWN,
                    finger_id=5,
                    x=goten_rect.centerx / resolution[0],
                    y=goten_rect.centery / resolution[1],
                )
            ],
        )
        self.assertEqual(menu.selected_character, "goten")
        self.assertTrue(menu.isPlaying)

        menu = Menu(resolution)
        options_center = (resolution[0] - 520, resolution[1] / 1.35)
        menu.launch_menu(
            screen,
            resolution,
            [
                pygame.event.Event(
                    pygame.FINGERDOWN,
                    finger_id=4,
                    x=options_center[0] / resolution[0],
                    y=options_center[1] / resolution[1],
                )
            ],
        )
        self.assertEqual(menu.state, State.OPTIONS)

    def test_keyboard_can_cycle_and_confirm_character_selection(self):
        resolution = (1200, 1000)
        screen = pygame.Surface(resolution)
        menu = Menu(resolution)
        menu.launch_menu(
            screen,
            resolution,
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
        )
        self.assertEqual(menu.state, State.CHARACTER_SELECT)

        menu.launch_menu(
            screen,
            resolution,
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RIGHT)],
        )
        self.assertEqual(menu.selected_character, "goten")

        menu.launch_menu(
            screen,
            resolution,
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)],
        )
        self.assertTrue(menu.isPlaying)


if __name__ == "__main__":
    unittest.main()
