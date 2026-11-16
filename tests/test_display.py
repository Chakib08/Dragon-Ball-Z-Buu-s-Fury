import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import game
from dialog.dialogbox import DialogBox
from map import MapManager
from menu import Menu, State
from utils.config import Config


class DisplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_fullscreen_asks_for_the_native_display_size(self):
        native = pygame.Surface((2400, 1080))
        with patch("game.pygame.display.set_mode", return_value=native) as set_mode:
            screen = game.create_display((1200, 1000), fullscreen=True)
        set_mode.assert_called_once_with((0, 0), pygame.FULLSCREEN)
        self.assertEqual(screen.get_size(), (2400, 1080))

    def test_windowed_mode_uses_the_configured_size(self):
        with patch("game.pygame.display.set_mode", return_value=pygame.Surface((1200, 1000))) as set_mode:
            with patch("game.is_android", return_value=False):
                game.create_display((1200, 1000), fullscreen=False)
        set_mode.assert_called_once_with((1200, 1000))

    def test_android_is_always_fullscreen(self):
        with patch("game.pygame.display.set_mode", return_value=pygame.Surface((2400, 1080))) as set_mode:
            with patch("game.is_android", return_value=True):
                game.create_display((1200, 1000), fullscreen=False)
        set_mode.assert_called_once_with((0, 0), pygame.FULLSCREEN)

    def test_falls_back_to_a_window_when_fullscreen_is_unavailable(self):
        window = pygame.Surface((1200, 1000))
        with patch("game.pygame.display.set_mode", side_effect=[pygame.error("no fullscreen"), window]) as set_mode:
            screen = game.create_display((1200, 1000), fullscreen=True)
        self.assertIs(screen, window)
        self.assertEqual(set_mode.call_args_list[-1].args, ((1200, 1000),))

    def test_map_zoom_shows_the_same_amount_of_map_on_any_screen(self):
        self.assertEqual(MapManager.zoom_for((1200, 1000)), 4)
        self.assertEqual(MapManager.zoom_for((2400, 1080)), 4)
        self.assertEqual(MapManager.zoom_for((1280, 720)), 3)
        self.assertEqual(MapManager.zoom_for((2560, 1440)), 6)

    def test_dialog_box_fits_on_every_screen_size(self):
        for size in ((1200, 1000), (2400, 1080), (1280, 720), (800, 480)):
            with self.subTest(size=size):
                dialog = DialogBox(size)
                right = dialog.x + dialog.box.get_width() + dialog.portrait.get_width()
                bottom = dialog.y + dialog.box.get_height()
                self.assertGreaterEqual(dialog.x, 0)
                self.assertGreaterEqual(dialog.y, 0)
                self.assertLessEqual(right, size[0])
                self.assertLessEqual(bottom, size[1])

    def test_menu_start_button_can_be_tapped_on_a_wide_screen(self):
        size = (2400, 1080)
        screen = pygame.Surface(size)
        menu = Menu(size)
        start = (round(size[0] * Menu.BUTTONS_X), round(size[1] / 1.5))
        tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start)
        menu.launch_menu(screen, size, [tap])
        self.assertEqual(menu.state, State.CHARACTER_SELECT)


if __name__ == "__main__":
    unittest.main()
