"""The fight's controls as actions (controls.py)."""

import os
import unittest
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from controls import Controls
from menu import Menu


class FakeTouch:
    ACTIONS = ("attack", "special", "super", "tech_prev", "tech_next", "form_prev", "form_next")

    def __init__(self, tapped=(), blocking=False, running=False, special_held=False, stick=(0.0, 0.0)):
        self.tapped = set(tapped)
        self.blocking, self.running, self.special_held = blocking, running, special_held
        self.stick_vector = stick

    def consume_action(self, action):
        if action in self.tapped:
            self.tapped.discard(action)
            return True
        return False


def fake_pad(pressed=(), held=(), move=(0.0, 0.0), running=False):
    return SimpleNamespace(pressed=set(pressed), held=set(held), move_vector=move, running=running)


class Keys:
    """pygame.key.get_pressed() with these keys down."""

    def __init__(self, *down):
        self.down = set(down)

    def __getitem__(self, code):
        return code in self.down


def key_down(key, **extra):
    return pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0, **extra)


class ControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def read(self, controls=None, events=(), touch=None, pad=None, keys=None):
        return (controls or Controls()).read(list(events), touch or FakeTouch(), pad or fake_pad(), keys or Keys())

    def test_keyboard_touch_and_controller_give_the_same_actions(self):
        self.assertIn("attack", self.read(events=[key_down(pygame.K_a)]))
        self.assertIn("attack", self.read(touch=FakeTouch(tapped=["attack"])))
        self.assertIn("attack", self.read(pad=fake_pad(pressed=["a"])))
        for intent in (self.read(keys=Keys(pygame.K_f)), self.read(touch=FakeTouch(blocking=True)),
                       self.read(pad=fake_pad(held=["b"]))):
            self.assertTrue(intent.holds("guard"))
        self.assertTrue(self.read(pad=fake_pad(running=True)).holds("run"))
        self.assertEqual(self.read().pressed, set())

    def test_the_stick_wins_over_the_controller_and_the_controller_over_the_arrows(self):
        arrows = Keys(pygame.K_RIGHT)
        self.assertEqual(self.read(keys=arrows).move, (1, 0))
        self.assertEqual(self.read(keys=arrows, pad=fake_pad(move=(0.0, 1.0))).move, (0.0, 1.0))
        self.assertEqual(self.read(keys=arrows, pad=fake_pad(move=(0.0, 1.0)),
                                   touch=FakeTouch(stick=(-0.5, 0.0))).move, (-0.5, 0.0))

    def test_a_touch_press_counts_once(self):
        touch = FakeTouch(tapped=["special"])
        self.assertIn("special", self.read(touch=touch))
        self.assertNotIn("special", self.read(touch=touch))

    def test_keys_and_buttons_can_be_changed_and_bad_names_are_ignored(self):
        controls = Controls({"keys": {"attack": ["j"], "guard": ["k", "left shift"], "talk": ["no such key"],
                                      "fly": ["g"]},
                             "pad": {"special": "rb"}})
        self.assertIn("attack", self.read(controls, events=[key_down(pygame.K_j)]))
        self.assertNotIn("attack", self.read(controls, events=[key_down(pygame.K_a)]))
        self.assertTrue(self.read(controls, keys=Keys(pygame.K_LSHIFT)).holds("guard"))
        self.assertIn("talk", self.read(controls, events=[key_down(pygame.K_t)]))  # kept
        self.assertNotIn("fly", controls.keys)
        self.assertIn("special", self.read(controls, pad=fake_pad(pressed=["rb"])))
        self.assertEqual(Controls("not a dict").keys, Controls().keys)

    def test_the_controls_guide_shows_the_keys_in_use(self):
        menu = Menu((1200, 800), Controls({"keys": {"attack": ["j"]}, "pad": {"guard": ["lb"]}}))
        guide = "\n".join(menu.controls_guide())
        self.assertIn("Attack: J or", guide)
        self.assertIn("LB guard", guide)


if __name__ == "__main__":
    unittest.main()
