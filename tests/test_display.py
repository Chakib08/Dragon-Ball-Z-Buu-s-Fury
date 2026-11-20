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
from result_screen import ResultScreen
from utils.config import Config

from average_stats import steady_module_fixtures

# Repeatable NPCs: no lucky dodges or blocks (see average_stats.py)
setUpModule, tearDownModule = steady_module_fixtures()



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

    def test_android_falls_back_to_native_full_screen_without_scaling(self):
        native = pygame.Surface((2400, 1080))
        with patch("game.is_android", return_value=True), \
                patch("game.pygame.display.set_mode",
                      side_effect=[pygame.error("no SCALED"), native]) as set_mode:
            screen = game.create_display((1200, 1000), fullscreen=False)
        self.assertIs(screen, native)
        self.assertEqual(set_mode.call_args_list[-1].args, ((0, 0), pygame.FULLSCREEN))

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
        start = menu.item_rects["arcade"].center
        tap = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=start)
        menu.launch_menu(screen, size, [tap])
        self.assertEqual(menu.state, State.CHARACTER_SELECT)


    def test_switching_screen_mid_game_redraws_on_the_new_surface(self):
        game_ = game.Game((1200, 1000), "test")
        game_.menu = game.Menu(game_.resolution)
        game_.dialogBox.open(["Hello"])
        for size in ((1280, 720), (2400, 1080), (1200, 1000)):
            with self.subTest(size=size):
                game_.set_screen(pygame.display.set_mode(size))
                self.assertEqual(game_.resolution, size)
                self.assertEqual(game_.map_manager.screen, game_.screen)
                self.assertEqual(game_.map_manager.combat.screen_size, size)
                self.assertEqual(game_.touch_controls.screen_size, size)
                self.assertEqual(game_.quit_prompt.screen_size, size)
                self.assertTrue(game_.dialogBox.isBoxOpened)
                layer = game_.map_manager.get_group()._map_layer
                self.assertEqual(layer.zoom, game.MapManager.zoom_for(size))
                # A whole frame and the menu draw without touching a stale surface
                for _ in range(3):
                    game_.play_frame([], False)
                game_.menu.launch_menu(game_.screen, game_.resolution, [])
                game_.quit_prompt.draw(game_.screen)

    def test_resizing_keeps_what_each_screen_shows_and_lays_it_out_again(self):
        game_ = game.Game((1200, 1000), "test")
        game_.menu = game.Menu(game_.resolution)
        menu = game_.menu
        menu.state = State.CHARACTER_SELECT
        menu.selected_character = "trunks"
        menu.selected_enemies = ["broly", "vegeta"]
        game_.quit_prompt.is_open = True
        game_.scene = "story"
        game_.result = ResultScreen(game_.resolution, victory=True)
        touch, prompt, result = game_.touch_controls, game_.quit_prompt, game_.result

        game_.set_screen(pygame.display.set_mode((2400, 1080)))

        # The same objects, laid out for the new size
        self.assertIs(game_.menu, menu)
        self.assertIs(game_.touch_controls, touch)
        self.assertIs(game_.quit_prompt, prompt)
        self.assertIs(game_.result, result)
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        self.assertEqual((menu.selected_character, menu.selected_enemies), ("trunks", ["broly", "vegeta"]))
        self.assertEqual(menu.main_image.get_size(), (2400, 1080))
        self.assertTrue(prompt.is_open)
        self.assertEqual(prompt.panel.center, (1200, 540))
        self.assertEqual(result.panel.center, (1200, 540))
        self.assertGreater(touch.buttons["attack"][0], 1200)
        self.assertEqual(game_.scene, "story")

    def test_toggling_full_screen_asks_for_the_other_mode(self):
        game_ = game.Game((1200, 1000), "test")
        with patch("game.create_display", return_value=pygame.display.set_mode((1280, 720))) as create:
            with patch.object(game.Game, "is_fullscreen", new_callable=lambda: property(lambda self: False)):
                game_.toggle_fullscreen()
        create.assert_called_once_with((1200, 1000), True)
        self.assertEqual(game_.resolution, (1280, 720))


    def test_android_draws_small_and_lets_the_gpu_scale_it(self):
        info = type("Info", (), {"current_w": 2400, "current_h": 1080})()
        with patch("game.is_android", return_value=True), \
                patch("game.pygame.display.Info", return_value=info), \
                patch("game.pygame.display.set_mode", return_value=pygame.Surface((1200, 540))) as set_mode:
            screen = game.create_display((1200, 1000), fullscreen=False)
        set_mode.assert_called_once_with((1200, 540), pygame.FULLSCREEN | pygame.SCALED)
        self.assertEqual(screen.get_size(), (1200, 540))

    def test_android_render_size_keeps_the_screen_shape_in_landscape(self):
        self.assertEqual(game.android_render_size((2400, 1080)), (1200, 540))
        self.assertEqual(game.android_render_size((1080, 2400)), (1200, 540))  # reported in portrait
        self.assertEqual(game.android_render_size((1920, 1080)), (960, 540))
        self.assertEqual(game.android_render_size((800, 480)), (800, 480))  # already small
        # The map is then zoomed 2x instead of 4x
        self.assertEqual(game.MapManager.zoom_for((1200, 540)), 2)


if __name__ == "__main__":
    unittest.main()
