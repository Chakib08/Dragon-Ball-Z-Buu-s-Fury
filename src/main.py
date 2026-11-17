import faulthandler

from utils.config import Config
from game import Game


def main():
    # If pygame ever crashes (segmentation fault), print the Python lines
    # that led to it instead of dying silently
    faulthandler.enable()
    Config.init()
    resolution = (Config.WIDTH, Config.HEIGHT)
    caption = Config.CAPTION
    app = Game(resolution, caption, fullscreen=Config.FULLSCREEN)
    app.run()


if __name__ == '__main__':
    main()
