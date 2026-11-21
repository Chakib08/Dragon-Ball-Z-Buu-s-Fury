import os
import unittest
from unittest.mock import patch

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

    def finger_at(self, event_type, finger_id, position):
        return pygame.event.Event(
            event_type, finger_id=finger_id, x=position[0] / 1200, y=position[1] / 1000
        )

    def test_stick_moves_in_any_direction_and_recentres_on_release(self):
        cx, cy = self.controls.stick_center
        r = self.controls.stick_radius
        self.controls.handle_event(self.finger_at(pygame.FINGERDOWN, 1, (cx, cy)))
        self.assertEqual(self.controls.stick_vector, (0.0, 0.0))  # dead zone

        # Up and to the right, half way: walking diagonally
        self.controls.handle_event(self.finger_at(pygame.FINGERMOTION, 1, (cx + r * 0.35, cy - r * 0.35)))
        dx, dy = self.controls.stick_vector
        self.assertAlmostEqual(dx, 0.35, places=2)
        self.assertAlmostEqual(dy, -0.35, places=2)
        self.assertFalse(self.controls.running)

        # Dragged far outside the base: the knob stops at the edge, running
        self.controls.handle_event(self.finger_at(pygame.FINGERMOTION, 1, (cx - r * 3, cy)))
        self.assertAlmostEqual(self.controls.stick_vector[0], -1.0, places=2)
        self.assertTrue(self.controls.running)

        self.controls.handle_event(self.finger_at(pygame.FINGERUP, 1, (cx - r * 3, cy)))
        self.assertEqual(self.controls.stick_vector, (0.0, 0.0))
        self.assertEqual(self.controls.stick_position, self.controls.stick_center)

    def test_stick_and_buttons_work_at_the_same_time(self):
        cx, cy = self.controls.stick_center
        r = self.controls.stick_radius
        self.controls.handle_event(self.finger_at(pygame.FINGERDOWN, 1, (cx + r, cy)))
        self.controls.handle_event(self.finger_event(pygame.FINGERDOWN, 2, "attack"))
        self.assertTrue(self.controls.consume_action("attack"))
        self.assertGreater(self.controls.stick_vector[0], 0.9)
        # Sliding the stick finger over a button does not press it
        self.controls.handle_event(self.finger_event(pygame.FINGERMOTION, 1, "special"))
        self.assertFalse(self.controls.consume_action("special"))

    def test_mouse_can_drag_the_stick(self):
        cx, cy = self.controls.stick_center
        self.controls.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(round(cx), round(cy))))
        self.controls.handle_event(pygame.event.Event(
            pygame.MOUSEMOTION, pos=(round(cx), round(cy + self.controls.stick_radius)), buttons=(1, 0, 0)
        ))
        self.assertGreater(self.controls.stick_vector[1], 0.9)

    def test_all_buttons_are_the_same_size(self):
        self.assertEqual(
            {self.controls.radius(control) for control in self.controls.buttons}, {self.controls.radius("attack")}
        )
        self.assertEqual(set(self.controls.buttons), {"attack", "block", "special", "super"})

    def test_block_is_held_not_pressed(self):
        self.controls.handle_event(self.finger_event(pygame.FINGERDOWN, 4, "block"))
        self.assertTrue(self.controls.blocking)
        self.assertFalse(self.controls.consume_action("block"))
        self.controls.handle_event(self.finger_event(pygame.FINGERUP, 4, "block"))
        self.assertFalse(self.controls.blocking)

    def test_every_button_uses_its_artwork_cut_to_a_circle(self):
        for control in ("attack", "block", "super", "special"):
            with self.subTest(control=control):
                normal, pressed = self.controls.button_surfaces[control]
                size = normal.get_width()
                self.assertEqual(size, int(self.controls.radius(control)) * 2)
                # The square image's black corners are cut away
                self.assertEqual(normal.get_at((2, 2)).a, 0)
                center = normal.get_at((size // 2, size // 3))
                self.assertGreaterEqual(center.a, 240)  # nearly opaque (some art is)
                # Pressed looks darker
                self.assertLess(sum(pressed.get_at((size // 2, size // 3))[:3]), sum(center[:3]))

    def test_buttons_are_drawn_when_the_artwork_is_missing(self):
        with patch("touch_controls.os.path.exists", return_value=False):
            controls = TouchControls((1200, 1000))
        surface = controls.button_surfaces["attack"][0]
        size = surface.get_width()
        white = sum(
            1 for x in range(size) for y in range(size) if surface.get_at((x, y))[:3] == (255, 255, 255)
        )
        self.assertGreater(white, size * size * 0.05)

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

    def test_controls_stay_on_screen_and_apart_on_phone_and_desktop_sizes(self):
        for size in ((1200, 1000), (2400, 1080), (1280, 720), (1920, 1080), (3200, 1440), (800, 480)):
            with self.subTest(size=size):
                controls = TouchControls(size)
                screen = pygame.Rect((0, 0), size)
                for control, (x, y) in controls.buttons.items():
                    radius = controls.radius(control)
                    self.assertTrue(screen.contains(pygame.Rect(x - radius, y - radius, radius * 2, radius * 2)), control)
                    self.assertEqual(controls._control_at((x, y)), control)
                    self.assertFalse(controls._on_stick((x, y)), control)
                # Buttons never overlap each other
                items = list(controls.buttons.items())
                for i, (a, pa) in enumerate(items):
                    for b, pb in items[i + 1:]:
                        self.assertGreater(
                            ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5,
                            controls.radius(a) + controls.radius(b), (a, b),
                        )
                cx, cy = controls.stick_center
                r = controls.stick_radius
                self.assertTrue(screen.contains(pygame.Rect(cx - r, cy - r, r * 2, r * 2)))
        self.assertGreater(TouchControls((3200, 1440)).button_size, TouchControls((1200, 1000)).button_size)

    def test_controls_render_on_screen(self):
        screen = pygame.Surface((1200, 1000))
        self.controls.draw(screen)
        center = tuple(round(value) for value in self.controls.buttons["attack"])
        self.assertNotEqual(screen.get_at(center)[:3], (0, 0, 0))

    def test_mouse_actions_work_and_focus_loss_clears_all_state(self):
        x, y = self.controls.buttons["special"]
        self.controls.handle_event(
            pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                button=1,
                pos=(round(x), round(y)),
            )
        )
        self.assertTrue(self.controls.consume_action("special"))
        self.controls.handle_event(
            pygame.event.Event(pygame.WINDOWFOCUSLOST)
        )

        self.assertEqual(self.controls.pointers, {})
        self.assertFalse(self.controls.consume_action("special"))

    def test_buttons_form_an_even_two_by_two_grid(self):
        b = self.controls.buttons
        self.assertEqual(b["super"][0], b["block"][0])
        self.assertEqual(b["special"][0], b["attack"][0])
        self.assertEqual(b["super"][1], b["special"][1])
        self.assertEqual(b["block"][1], b["attack"][1])
        self.assertAlmostEqual(b["attack"][0] - b["block"][0], b["attack"][1] - b["special"][1])
        # Attack sits in the bottom-right corner
        self.assertEqual(max(b.values()), b["attack"])

    def test_character_selection_and_options_can_be_opened_by_touch(self):
        resolution = (1200, 1000)
        screen = pygame.Surface(resolution)
        menu = Menu(resolution)
        start_center = menu.item_rects["arcade"].center
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
        vegeta_rect = menu.character_rects["vegeta"]
        menu.launch_menu(
            screen,
            resolution,
            [
                pygame.event.Event(
                    pygame.FINGERDOWN,
                    finger_id=5,
                    x=vegeta_rect.centerx / resolution[0],
                    y=vegeta_rect.centery / resolution[1],
                )
            ],
        )
        self.assertEqual(menu.selected_character, "vegeta")
        self.assertFalse(menu.isPlaying)
        # A first tap shows Vegeta on the right; a second one chooses him
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        menu.launch_menu(screen, resolution, [])
        menu.launch_menu(screen, resolution, [pygame.event.Event(
            pygame.FINGERDOWN, finger_id=7, x=vegeta_rect.centerx / resolution[0],
            y=vegeta_rect.centery / resolution[1])])

        def tap(rect):
            menu.launch_menu(screen, resolution, [])  # lays the screen out
            menu.launch_menu(screen, resolution, [pygame.event.Event(
                pygame.FINGERDOWN, finger_id=6, x=rect.centerx / resolution[0], y=rect.centery / resolution[1])])

        # Then the allies: tapping toggles a card, Vegeta (the player) can't be one
        self.assertEqual(menu.state, State.ALLY_SELECT)
        menu.launch_menu(screen, resolution, [])
        tap(menu.character_rects["vegeta"])
        self.assertEqual(menu.selected_allies, [])
        tap(menu.character_rects["goku"])
        tap(menu.character_rects["trunks"])
        self.assertEqual(menu.selected_allies, ["goku", "trunks"])
        tap(menu.continue_rect)
        # Then the opponents, several of them
        self.assertEqual(menu.state, State.ENEMY_SELECT)
        tap(menu.character_rects["broly"])
        tap(menu.character_rects["gohan"])  # was picked by default: unpicked
        tap(menu.character_rects["vegeta"])
        self.assertEqual(menu.selected_enemies, ["broly", "vegeta"])
        self.assertFalse(menu.isPlaying)
        tap(menu.continue_rect)
        self.assertEqual(menu.state, State.MAP_SELECT)
        tap(menu.continue_rect)  # Fight! on the arena screen
        self.assertTrue(menu.isPlaying)
        self.assertEqual(menu.selected_character, "vegeta")

        menu = Menu(resolution)
        options_center = menu.item_rects["options"].center
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
        key = lambda k: menu.launch_menu(screen, resolution, [pygame.event.Event(pygame.KEYDOWN, key=k)])
        key(pygame.K_RETURN)
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        key(pygame.K_RIGHT)
        self.assertEqual(menu.selected_character, "vegeta")
        key(pygame.K_RETURN)

        # Allies: none, Enter goes on (fight alone)
        self.assertEqual(menu.state, State.ALLY_SELECT)
        self.assertFalse(menu.isPlaying)
        key(pygame.K_RETURN)
        self.assertEqual(menu.state, State.ENEMY_SELECT)
        self.assertEqual(menu.selected_allies, [])

        # Esc goes back one screen at a time
        key(pygame.K_ESCAPE)
        self.assertEqual(menu.state, State.ALLY_SELECT)
        key(pygame.K_ESCAPE)
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        key(pygame.K_RETURN)

        # Allies: the cursor starts on the player's card (unavailable); Space picks
        key(pygame.K_RIGHT)
        key(pygame.K_SPACE)
        self.assertEqual(menu.selected_allies, ["gohan"])
        key(pygame.K_RETURN)

        # Opponents: Gohan by default; up to 4, a fifth replaces the first
        self.assertEqual(menu.state, State.ENEMY_SELECT)
        self.assertEqual(menu.selected_enemies, ["gohan"])
        for name in ("trunks", "broly", "goku"):
            menu.focus = menu.character_names.index(name)
            key(pygame.K_SPACE)
        self.assertEqual(menu.selected_enemies, ["gohan", "trunks", "broly", "goku"])
        menu.focus = menu.character_names.index("vegeta")
        key(pygame.K_SPACE)
        self.assertEqual(menu.selected_enemies, ["trunks", "broly", "goku", "vegeta"])
        # With none picked, Enter picks the card under the cursor and starts
        menu.selected_enemies.clear()
        menu.focus = menu.character_names.index("broly")
        key(pygame.K_RETURN)
        self.assertEqual(menu.selected_enemies, ["broly"])
        self.assertEqual(menu.state, State.MAP_SELECT)  # then the arena
        key(pygame.K_RETURN)
        self.assertTrue(menu.isPlaying)
        self.assertEqual(menu.selected_character, "vegeta")
        self.assertEqual(menu.selected_allies, ["gohan"])

    def android_tap(self, menu, screen, resolution, rect, copy_next_frame=False):
        """A touch as Android reports it: FINGERDOWN, plus a MOUSEBUTTONDOWN
        copy (touch=True) in the same frame, or in the next one."""
        x, y = rect.center
        finger = pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / resolution[0], y=y / resolution[1])
        copy = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(int(x), int(y)), touch=True)
        menu.launch_menu(screen, resolution, [])  # lays the screen out
        if copy_next_frame:
            menu.launch_menu(screen, resolution, [finger])
            menu.launch_menu(screen, resolution, [copy])
        else:
            menu.launch_menu(screen, resolution, [finger, copy])

    def test_android_touches_pick_allies_and_opponents_once(self):
        for copy_next_frame in (False, True):
            with self.subTest(copy_next_frame=copy_next_frame):
                resolution = (1200, 540)
                screen = pygame.Surface(resolution)
                menu = Menu(resolution)
                menu.state = State.CHARACTER_SELECT
                tap = lambda rect: self.android_tap(menu, screen, resolution, rect, copy_next_frame)
                menu.launch_menu(screen, resolution, [])
                tap(menu.character_rects["goku"])
                self.assertEqual(menu.state, State.CHARACTER_SELECT)  # shown, not chosen yet
                tap(menu.character_rects["goku"])
                self.assertEqual(menu.state, State.ALLY_SELECT)
                self.assertEqual(menu.selected_allies, [])  # the copy did not land on a card
                tap(menu.character_rects["vegeta"])
                tap(menu.character_rects["trunks"])
                self.assertEqual(menu.selected_allies, ["vegeta", "trunks"])  # picked, not undone
                tap(menu.continue_rect)
                # The copy did not press "Fight!" on the next screen
                self.assertEqual(menu.state, State.ENEMY_SELECT)
                self.assertFalse(menu.isPlaying)
                tap(menu.character_rects["broly"])
                self.assertEqual(menu.selected_enemies, ["gohan", "broly"])
                tap(menu.character_rects["gohan"])
                self.assertEqual(menu.selected_enemies, ["broly"])
                tap(menu.continue_rect)
                self.assertEqual(menu.state, State.MAP_SELECT)
                self.assertFalse(menu.isPlaying)  # the copy did not press Fight!
                tap(menu.continue_rect)
                self.assertTrue(menu.isPlaying)

    def test_a_plain_mouse_click_still_works(self):
        from taps import tap_position
        click = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 20))
        self.assertEqual(tap_position(click, (100, 100)), (10, 20))
        copy = pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(10, 20), touch=True)
        self.assertIsNone(tap_position(copy, (100, 100)))

    def test_back_button_on_every_selection_screen(self):
        """Touch screens have no Esc: a Back button goes one screen back."""
        resolution = (1200, 540)
        screen = pygame.Surface(resolution)
        menu = Menu(resolution)

        def tap_back():
            menu.launch_menu(screen, resolution, [])  # lays the screen out
            x, y = menu.back_rect.center
            menu.launch_menu(screen, resolution, [
                pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / resolution[0], y=y / resolution[1])])

        menu.state = State.ENEMY_SELECT
        tap_back()
        self.assertEqual(menu.state, State.ALLY_SELECT)
        tap_back()
        self.assertEqual(menu.state, State.CHARACTER_SELECT)
        tap_back()
        self.assertEqual(menu.state, State.START)
        self.assertFalse(menu.isPlaying)
        # From an online choice too, which it cancels
        menu.open_online()
        tap_back()
        self.assertEqual(menu.state, State.START)
        self.assertFalse(menu.online)

    def test_the_back_button_does_not_cover_the_cards(self):
        for resolution in ((1200, 540), (800, 480), (2400, 1080)):
            menu = Menu(resolution)
            for state in (State.CHARACTER_SELECT, State.ALLY_SELECT, State.ENEMY_SELECT):
                menu.state = state
                menu.launch_menu(pygame.Surface(resolution), resolution, [])
                with self.subTest(resolution=resolution, state=state):
                    self.assertTrue(pygame.Rect((0, 0), resolution).contains(menu.back_rect))
                    self.assertEqual(menu.back_rect.collidelist(list(menu.character_rects.values())), -1)
                    if menu.continue_rect is not None:
                        self.assertFalse(menu.back_rect.colliderect(menu.continue_rect))

    def main_menu(self, resolution=(1200, 540)):
        screen = pygame.Surface(resolution)
        menu = Menu(resolution)
        run = lambda events=(): menu.launch_menu(screen, resolution, list(events))
        run()
        return menu, run

    def test_main_menu_has_the_four_modes_in_order(self):
        menu, _ = self.main_menu()
        self.assertEqual([item for item, _, _ in Menu.MAIN_ITEMS], ["story", "arcade", "online", "options"])
        self.assertEqual(Menu.MAIN_ITEMS[menu.selected_item][0], "arcade")  # highlighted at first
        rects = [menu.item_rects[item] for item, _, _ in Menu.MAIN_ITEMS]
        for index, rect in enumerate(rects):
            self.assertEqual(rect.collidelist(rects[index + 1:]), -1)
            self.assertTrue(pygame.Rect(0, 0, 1200, 540).contains(rect))

    def test_story_mode_says_it_is_not_available_yet(self):
        menu, run = self.main_menu()
        run([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP)])
        run([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)])
        self.assertTrue(menu.notice_shown)
        self.assertEqual(menu.state, State.START)
        self.assertFalse(menu.isPlaying)
        # Any key or tap closes it, and does nothing else
        run([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN)])
        self.assertFalse(menu.notice_shown)
        self.assertEqual(menu.state, State.START)

    def test_arcade_online_and_options_open_their_screens(self):
        for item, state, online in (("arcade", State.CHARACTER_SELECT, False),
                                    ("online", State.NAME_ENTRY, True),
                                    ("options", State.OPTIONS, False)):
            with self.subTest(item=item):
                menu, run = self.main_menu()
                x, y = menu.item_rects[item].center
                run([pygame.event.Event(pygame.FINGERDOWN, finger_id=1, x=x / 1200, y=y / 540)])
                self.assertEqual(menu.state, state)
                self.assertEqual(menu.online, online)

    def test_keyboard_and_mouse_move_the_highlight(self):
        menu, run = self.main_menu()
        run([pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN)] * 3)  # wraps around
        self.assertEqual(Menu.MAIN_ITEMS[menu.selected_item][0], "story")
        run([pygame.event.Event(pygame.MOUSEMOTION, pos=menu.item_rects["options"].center, rel=(0, 0), buttons=(0, 0, 0))])
        self.assertEqual(Menu.MAIN_ITEMS[menu.selected_item][0], "options")
        self.assertEqual(menu.state, State.START)  # pointing is not choosing

    def test_the_menu_no_longer_uses_the_old_images(self):
        import inspect
        import menu as menu_module
        source = inspect.getsource(menu_module)
        for old in ("start-active", "start-inactive", "options-active", "options-inactive", "arrow.png",
                    "menu_image_box"):
            self.assertNotIn(old, source)

    def test_main_menu_shows_the_version_the_android_app_gets(self):
        import configparser
        import re
        from version import __version__
        resolution = (1200, 540)
        screen = pygame.Surface(resolution)
        menu = Menu(resolution)
        menu.launch_menu(screen, resolution, [])
        self.assertEqual(menu.version_text, f"v{__version__}")
        # Drawn in the bottom-left corner, inside the screen
        label = menu._version_label
        self.assertIsNotNone(label)
        self.assertLess(label.get_width(), resolution[0] // 4)
        # buildozer.spec reads the same number from src/version.py
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        spec = configparser.ConfigParser()
        spec.read(os.path.join(root, "buildozer.spec"))
        self.assertFalse(spec.has_option("app", "version"))
        with open(os.path.join(root, "src", "version.py")) as file:
            found = re.search(spec.get("app", "version.regex"), file.read())
        self.assertEqual(found.group(1), __version__)

    def test_online_asks_the_name_then_the_character_and_allies_but_no_opponents(self):
        resolution = (1200, 1000)
        screen = pygame.Surface(resolution)
        key = lambda code: pygame.event.Event(pygame.KEYDOWN, key=code)
        saved = {}
        with patch("menu.user_settings.load", return_value={}), \
                patch("menu.user_settings.save", side_effect=saved.update):
            menu = Menu(resolution)
            menu.open_online()
            self.assertEqual(menu.state, State.NAME_ENTRY)
            typed = [pygame.event.Event(pygame.TEXTINPUT, text=part) for part in ("Chak", "ib!", "\x07")]
            menu.launch_menu(screen, resolution, typed + [key(pygame.K_BACKSPACE), key(pygame.K_RETURN)])
            self.assertEqual(menu.player_name, "Chakib")
            self.assertEqual(saved["player_name"], "Chakib")  # remembered for next time
            self.assertEqual(menu.state, State.CHARACTER_SELECT)
            menu.launch_menu(screen, resolution, [key(pygame.K_RETURN)])  # Goku
            self.assertEqual(menu.state, State.ALLY_SELECT)
            menu.focus = menu.character_names.index("vegeta")
            menu.launch_menu(screen, resolution, [key(pygame.K_SPACE), key(pygame.K_RETURN)])
            self.assertEqual(menu.state, State.MAP_SELECT)  # the arena of its rooms
            menu.launch_menu(screen, resolution, [key(pygame.K_RETURN)])
        self.assertTrue(menu.isPlaying)
        self.assertTrue(menu.online)
        self.assertEqual(menu.selected_allies, ["vegeta"])

        # Back goes the same way in reverse
        menu.isPlaying = False
        for expected in (State.ALLY_SELECT, State.CHARACTER_SELECT, State.NAME_ENTRY, State.START):
            menu.go_back()
            self.assertEqual(menu.state, expected)
        self.assertFalse(menu.online)

    def test_an_empty_name_becomes_the_characters(self):
        with patch("menu.user_settings.load", return_value={}), patch("menu.user_settings.save"):
            menu = Menu((1200, 1000))
            menu.open_online()
            menu.player_name = "   "
            menu.confirm_name()
        self.assertEqual(menu.player_name, "Goku")

    def test_every_character_card_has_a_portrait_and_its_stats(self):
        import portraits
        from stats import character_stats
        resolution = (1200, 540)
        menu = Menu(resolution)
        for name in menu.character_names:
            with self.subTest(character=name):
                face = portraits.portrait(name)
                self.assertIsNotNone(face)
                self.assertEqual(face.get_size(), (64, 64))
                if name == "goku":  # Buu's Fury frames have rounded corners
                    self.assertIsNotNone(face.get_colorkey())
        self.assertIsNone(portraits.portrait("no such character"))
        # Broly hits harder than Trunks, and the card says so
        self.assertGreater(character_stats("broly").power, character_stats("trunks").power)
        drawn = []

        class Recording:
            """A font that notes what it writes."""
            def __init__(self, font):
                self.font = font

            def render(self, text, *rest):
                drawn.append(text)
                return self.font.render(text, *rest)

            def __getattr__(self, name):
                return getattr(self.font, name)

        menu._fitted_previews[("fonts", resolution[1])] = tuple(Recording(font)
                                                                for font in menu._fonts_for(resolution[1]))
        menu.state = State.CHARACTER_SELECT
        for name in ("broly", "trunks"):  # the focused one's stats on the right
            menu.selected_character = name
            menu.launch_menu(pygame.Surface(resolution), resolution, [])
        self.assertIn("Broly", drawn)
        self.assertIn("Choose Trunks", drawn)
        for label in ("POW", "HP", "DEF", "SPD", "130", "95"):
            self.assertIn(label, drawn)

    def test_the_portrait_grid_is_walked_with_the_arrows_and_the_mouse(self):
        resolution = (1200, 540)
        screen = pygame.Surface(resolution)
        key = lambda code: pygame.event.Event(pygame.KEYDOWN, key=code)
        menu = Menu(resolution)
        menu.state = State.ENEMY_SELECT
        menu.focus = 0
        menu.launch_menu(screen, resolution, [])
        columns = menu.grid_columns
        self.assertGreater(columns, 1)
        self.assertEqual(len(menu.character_rects), len(menu.character_names))
        menu.launch_menu(screen, resolution, [key(pygame.K_DOWN), key(pygame.K_RIGHT)])
        self.assertEqual(menu.focus, columns + 1)
        menu.launch_menu(screen, resolution, [key(pygame.K_UP)])
        self.assertEqual(menu.focus, 1)
        # The mouse pointing at a portrait shows it
        target = menu.character_names[-1]
        menu.launch_menu(screen, resolution, [pygame.event.Event(
            pygame.MOUSEMOTION, pos=menu.character_rects[target].center, rel=(0, 0), buttons=(0, 0, 0))])
        self.assertEqual(menu._focused(), target)
        self.assertEqual(menu.selected_enemies, ["gohan"])  # looking does not pick

    def test_opponent_screen_shows_each_enemys_difficulty(self):
        resolution = (1200, 1000)
        menu = Menu(resolution)
        self.assertEqual(menu.enemy_difficulties["broly"].name, "hard")
        self.assertEqual(menu.enemy_difficulties["gohan"].name, "normal")
        menu.state = State.ENEMY_SELECT
        menu.launch_menu(pygame.Surface(resolution), resolution, [])
        self.assertEqual(set(menu.character_rects), set(menu.character_names))


if __name__ == "__main__":
    unittest.main()
