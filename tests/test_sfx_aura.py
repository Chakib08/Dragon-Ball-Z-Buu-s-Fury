"""Sound effects (sfx.py) and the Super Saiyan aura (effects.Aura)."""

import os
import random
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import sfx
from combat import CombatSystem
from effects import Aura
from saiyan import Saiyan
from utils.config import Config
from average_stats import steady_module_fixtures

setUpModule, tearDownModule = steady_module_fixtures()

HAS_SOUNDS = os.path.isdir(os.path.join(os.path.dirname(__file__), "..", "Sounds", "sfx"))


@unittest.skipUnless(HAS_SOUNDS, "Sounds/sfx not installed (setup.sh)")
class SoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        try:
            pygame.mixer.init()
        except pygame.error:
            raise unittest.SkipTest("no audio device")
        sfx.reset()

    def setUp(self):
        sfx.reset()

    def test_a_group_plays_one_of_its_files(self):
        self.assertIn(sfx.play("melee"), ("melee-1", "melee-2"))
        self.assertEqual(sfx.play("ko"), "ko")

    def test_the_same_sound_is_not_repeated_at_once(self):
        self.assertIsNotNone(sfx.play("block"))
        self.assertIsNone(sfx.play("block"))  # a moment later: skipped

    def test_unknown_sounds_do_nothing(self):
        self.assertIsNone(sfx.play("no-such-sound"))

    def test_voices(self):
        self.assertEqual(sfx.voice_of("vegeta"), "voice-vegeta")
        self.assertIn(sfx.voice_of("vegito"), ("voice-adultgoku", "voice-vegeta"))
        self.assertIsNone(sfx.voice_of("cell_perfect"))
        self.assertTrue(sfx.play("voice-adultgoku", 0.5).startswith("voice-adultgoku-"))

    def test_sounds_leave_the_fights_random_numbers_alone(self):
        random.seed(7)
        expected = [random.random() for _ in range(3)]
        random.seed(7)
        sfx.play("melee")
        sfx.shout("vegito")
        self.assertEqual([random.random() for _ in range(3)], expected)


class AuraTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()
        pygame.display.set_mode((1200, 540))
        if not Aura.frames():
            raise unittest.SkipTest("Vegeta's effects sheet not installed (setup.sh)")

    def fight(self, name):
        player = Saiyan(200, 200, False, name)
        player.update()
        return player, CombatSystem(player, (1200, 540))

    def run_frames(self, player, combat, frames):
        for _ in range(frames):
            player.update_action()
            combat.update([], [])

    def test_every_super_saiyan_transformation_has_the_aura(self):
        for name in ("goku", "vegeta", "vegito", "gohan", "trunks", "goten", "kid_trunks", "piccolo"):
            with self.subTest(character=name):
                player, combat = self.fight(name)
                player.ki = player.max_ki
                self.assertTrue(player.transform())
                self.run_frames(player, combat, 1)
                auras = [e for e in combat.effects if isinstance(e, Aura)]
                self.assertEqual(len(auras), 1)
                aura = auras[0]
                # Around the fighter, behind it (the lower sprite is drawn in front)
                drawn = aura.rect.move(aura.image_offset())
                self.assertTrue(drawn.colliderect(player.rect))
                self.assertGreater(drawn.height, player.image.get_height())
                self.assertLess(aura.rect.bottom, player.rect.bottom)
                # It fades once the transformation is over
                self.run_frames(player, combat, 400)
                self.assertNotIn(aura, combat.effects)

    def test_an_aura_follows_a_big_fighter_at_its_size(self):
        small, combat = self.fight("goku")
        big, big_combat = self.fight("cell_perfect")
        self.assertGreater(Aura(big).image.get_height(), Aura(small).image.get_height())

    def test_powering_up_shows_it_too(self):
        # Gogeta is always a Super Saiyan: powering up (no transformation
        # frames) still flares the aura
        player, combat = self.fight("gogeta")
        self.run_frames(player, combat, 1)
        player.power_up()
        self.run_frames(player, combat, 1)
        self.assertTrue(any(isinstance(e, Aura) for e in combat.effects))


if __name__ == "__main__":
    unittest.main()
