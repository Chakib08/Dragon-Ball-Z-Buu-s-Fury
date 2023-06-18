import pygame
from game import Game

main_theme = "Sounds/DBZ-Buus-Fury-Soundtrack-Theme.wav"
resolution = (400, 400)
caption = "Dragon Ball Z Buu's Fury"
isAppRunning = True

if __name__ == '__main__':
    # Initialize Pygame
    pygame.init()
    
    app = Game(resolution, caption)
    app.play_music(main_theme, isAppRunning)
    app.run(isAppRunning)