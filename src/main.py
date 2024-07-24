from utils.config import Config
from game import Game

def main():
    Config.init()
    resolution = (Config.WIDTH, Config.HEIGHT)
    caption = Config.CAPTION
    app = Game(resolution, caption)
    app.run()

if __name__ == '__main__':
    main()