"""The game plays at the same speed whatever the frame rate (utils.timing)."""

import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from character import Character
from effects import Projectile, Spark
from utils import timing
from utils.config import Config
from average_stats import use_average_stats


def frames(fps, seconds):
    """Play `seconds` at `fps`: yields once per frame, with the clock set."""
    for _ in range(round(fps * seconds)):
        timing.advance(1000 / fps)
        yield


class TimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        Config.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        use_average_stats(self)
        self.addCleanup(timing.reset)

    def test_ticks_follow_the_frame_time_and_long_stalls_are_capped(self):
        timing.advance(1000 / 60)
        self.assertAlmostEqual(timing.ticks(), 1.0)
        timing.advance(1000 / 30)
        self.assertAlmostEqual(timing.ticks(), 2.0)
        timing.advance(2000)
        self.assertEqual(timing.ticks(), timing.MAX_TICKS)
        timing.reset()
        self.assertEqual(timing.ticks(), 1.0)

    def walked(self, fps):
        character = Character(100, 100, "goku")
        for _ in frames(fps, 1):
            character.move("Walk Right", 4)
        return character.position[0] - 100

    def test_walking_covers_the_same_distance_at_30_60_and_120_fps(self):
        at_60 = self.walked(60)
        self.assertAlmostEqual(self.walked(30), at_60, places=6)
        self.assertAlmostEqual(self.walked(120), at_60, places=6)

    def test_a_walk_cycle_plays_at_the_same_pace(self):
        def frame_after(fps):
            character = Character(100, 100, "goku")
            for _ in frames(fps, 0.5):
                character.move("Walk Right", 4)
            return character.animator.current_animation_index

        self.assertEqual(frame_after(30), frame_after(60))

    def test_a_knockback_pushes_as_far_at_any_frame_rate(self):
        def pushed(fps):
            character = Character(100, 100, "goku")
            character.update()
            character.push_from((character.feet.centerx - 10, character.feet.centery))
            for _ in frames(fps, 0.5):
                character.update_knockback([])
            return character.position[0] - 100

        at_60 = pushed(60)
        self.assertGreater(at_60, 0)
        self.assertAlmostEqual(pushed(25), at_60, places=6)
        self.assertAlmostEqual(pushed(144), at_60, places=6)

    def test_one_shot_actions_last_as_long(self):
        def busy_seconds(fps):
            character = Character(100, 100, "goku")
            self.assertTrue(character.start_action("hurt", "Hurt Right", clock_speed=12, hold_ticks=10))
            count = 0
            for _ in frames(fps, 3):
                if not character.update_action():
                    break
                count += 1
            return count / fps

        self.assertAlmostEqual(busy_seconds(30), busy_seconds(60), delta=0.05)

    def test_effects_fly_and_play_at_the_same_speed(self):
        frame = pygame.Surface((4, 4))

        def flown(fps):
            ball = Projectile([frame, frame], [frame], [0, 0], "Right", speed=3, max_range=10 ** 6,
                              damage=1, on_hit=None)
            for _ in frames(fps, 1):
                ball.update_effect(())
            return ball.travelled

        self.assertAlmostEqual(flown(30), flown(60), places=6)

        def spark_frames(fps):
            spark = Spark([frame] * 6, (0, 0))
            count = 0
            for _ in frames(fps, 2):
                spark.update_effect(())
                if spark.done:
                    break
                count += 1
            return count / fps

        self.assertAlmostEqual(spark_frames(30), spark_frames(60), delta=1 / 30)


if __name__ == "__main__":
    unittest.main()
