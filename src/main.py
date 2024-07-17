import pygame
from game import Game

resolution = (1200, 1000)
caption = "Dragon Ball Z Buu's Fury Pygame DP"

def main():
    pygame.init() 
    app = Game(resolution, caption)
    app.run()

if __name__ == '__main__':
    main()