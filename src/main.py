import faulthandler
import os
import sys

import pygame

import smoke
from utils.config import Config
from game import Game


def enable_crash_traces():
    """If pygame ever crashes (segmentation fault), print the Python lines
    that led to it. Needs a real file behind stderr: on Android stderr goes
    to the system log through an object without one, and asking for it
    there would stop the game before it starts."""
    try:
        sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        # io.UnsupportedOperation is an OSError and a ValueError
        return False
    faulthandler.enable()
    return True


# Set (e.g. DBZ_SMOKE_TEST=arcade) by the build pipelines to check a build:
# the game goes straight into an arcade fight, plays it for
# DBZ_SMOKE_TEST_SECONDS, then quits; any error ends it with a failure
SMOKE_TEST = "DBZ_SMOKE_TEST"


def main():
    enable_crash_traces()
    Config.init()
    resolution = (Config.WIDTH, Config.HEIGHT)
    caption = Config.CAPTION
    smoke_test = os.environ.get(SMOKE_TEST)
    try:
        app = Game(resolution, caption, fullscreen=Config.FULLSCREEN and not smoke_test)
        smoke.report(f"game created ({app.resolution[0]}x{app.resolution[1]})")
        if smoke_test:
            seconds = float(os.environ.get("DBZ_SMOKE_TEST_SECONDS", "5"))
            pygame.time.set_timer(pygame.QUIT, int(seconds * 1000), 1)
            app.start_in = smoke_test
        app.run()
    except BaseException:
        smoke.report_error()
        raise
    smoke.report(f"smoke test passed: {app.scene} scene, {app.character.character_name} "
                 f"on {app.map_manager.current_map}")


if __name__ == '__main__':
    main()
