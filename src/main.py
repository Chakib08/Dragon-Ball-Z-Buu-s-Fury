import faulthandler
import sys

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


def main():
    enable_crash_traces()
    Config.init()
    resolution = (Config.WIDTH, Config.HEIGHT)
    caption = Config.CAPTION
    app = Game(resolution, caption, fullscreen=Config.FULLSCREEN)
    app.run()


if __name__ == '__main__':
    main()
