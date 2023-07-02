import pygame
from game import Game

main_theme = "Sounds/DBZ-Buus-Fury-Soundtrack-Theme.wav"
resolution = (800, 800)
caption = "Dragon Ball Z Buu's Fury"
isAppRunning = True

# Tmx data
tmx_map = "Graphics/map.tmx"          

if __name__ == '__main__':
    # Initialize Pygame
    pygame.init()
    
    app = Game(resolution, caption, tmx_map)
    app.play_music(main_theme, isAppRunning)
    app.run(isAppRunning)   