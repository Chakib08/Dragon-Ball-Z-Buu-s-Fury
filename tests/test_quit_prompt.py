import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from quit_prompt import QuitPrompt
from touch_controls import TouchControls


def key(code):
    return pygame.event.Event(pygame.KEYDOWN, key=code)


def click(position):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(round(position[0]), round(position[1])))


class QuitPromptTests(unittest.TestCase):
    SIZE = (1200, 1000)

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.prompt = QuitPrompt(self.SIZE)

    def test_escape_asks_first_and_enter_confirms(self):
        self.assertEqual(self.prompt.process([key(pygame.K_ESCAPE)]), [])
        self.assertTrue(self.prompt.is_open)
        self.assertFalse(self.prompt.confirmed)

        self.prompt.process([key(pygame.K_RETURN)])
        self.assertTrue(self.prompt.confirmed)

    def test_escape_again_or_no_cancels(self):
        for cancel in (key(pygame.K_ESCAPE), key(pygame.K_n), click(self.prompt.no_rect.center)):
            with self.subTest(cancel=cancel):
                self.prompt.process([key(pygame.K_ESCAPE)])
                self.prompt.process([cancel])
                self.assertFalse(self.prompt.is_open)
                self.assertFalse(self.prompt.confirmed)

    def test_corner_button_opens_by_mouse_or_finger_and_yes_quits(self):
        x, y = self.prompt.button_center
        finger = pygame.event.Event(
            pygame.FINGERDOWN, finger_id=1, x=x / self.SIZE[0], y=y / self.SIZE[1]
        )
        for tap in (click((x, y)), finger):
            with self.subTest(tap=tap.type):
                prompt = QuitPrompt(self.SIZE)
                self.assertEqual(prompt.process([tap]), [])
                self.assertTrue(prompt.is_open)
                prompt.process([click(prompt.yes_rect.center)])
                self.assertTrue(prompt.confirmed)

    def test_game_gets_no_input_while_the_question_is_open(self):
        self.prompt.process([key(pygame.K_ESCAPE)])
        quit_event = pygame.event.Event(pygame.QUIT)
        remaining = self.prompt.process([key(pygame.K_a), click((600, 900)), quit_event])
        self.assertEqual(remaining, [quit_event])
        self.assertTrue(self.prompt.is_open)

    def test_other_input_passes_through_and_escape_can_be_left_to_the_menu(self):
        events = [key(pygame.K_a), click((300, 500))]
        self.assertEqual(self.prompt.process(events), events)
        escape = key(pygame.K_ESCAPE)
        self.assertEqual(self.prompt.process([escape], escape_opens=False), [escape])
        self.assertFalse(self.prompt.is_open)

    def test_button_and_dialog_fit_and_avoid_the_touch_controls_on_every_screen(self):
        for size in ((1200, 1000), (2400, 1080), (1280, 720), (800, 480)):
            with self.subTest(size=size):
                prompt = QuitPrompt(size)
                screen = pygame.Rect((0, 0), size)
                x, y = prompt.button_center
                self.assertTrue(screen.contains(pygame.Rect(x - prompt.radius, y - prompt.radius, prompt.radius * 2, prompt.radius * 2)))
                for rect in (prompt.panel, prompt.yes_rect, prompt.no_rect):
                    self.assertTrue(screen.contains(rect))
                self.assertFalse(prompt.yes_rect.colliderect(prompt.no_rect))
                controls = TouchControls(size)
                self.assertIsNone(controls._control_at((x, y)))
                for center in controls.buttons.values():
                    self.assertFalse(prompt._on_button(center))

    def test_draws_the_button_and_the_question(self):
        screen = pygame.Surface(self.SIZE)
        self.prompt.draw(screen)
        self.assertNotEqual(screen.get_at(self.prompt.button_center)[:3], (0, 0, 0))
        self.assertEqual(screen.get_at(self.prompt.panel.center)[:3], (0, 0, 0))
        self.prompt.process([key(pygame.K_ESCAPE)])
        self.prompt.draw(screen)
        self.assertEqual(screen.get_at(self.prompt.yes_rect.midtop)[:3], (245, 245, 245))


if __name__ == "__main__":
    unittest.main()
