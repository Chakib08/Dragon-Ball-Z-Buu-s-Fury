import pygame
from game import Game
from pathlib import Path

# Get the directory of the current file
current_dir = Path(__file__).resolve().parent

main_theme = current_dir.parent / "Sounds/DBZ-Buus-Fury-Soundtrack-Theme.wav"
resolution = (1000, 1000)
caption = "Dragon Ball Z Buu's Fury"

# Tmx data
tmx_map = current_dir.parent / 'Graphics/map.tmx'

if __name__ == '__main__':
    # Initialize Pygame
    pygame.init()
    
    app = Game(resolution, caption, tmx_map)
    app.play_music(main_theme)
    app.run()