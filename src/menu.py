import pygame
from pathlib import Path

class Menu:
    def __init__(self, resolution) -> None:
        current_path = Path(__file__).resolve().parent
        self.image_menu = pygame.image.load(current_path.parent / "Graphics/menu/menu_image.jpg")
        self.image_menu = pygame.transform.scale(self.image_menu, resolution)
        self.image_start = pygame.image.load(current_path.parent / "Graphics/menu/start-inactive.png")
        
    