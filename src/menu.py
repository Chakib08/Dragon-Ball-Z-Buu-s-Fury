import pygame
from pathmanager import PathManager

class Menu:
    def __init__(self, resolution) -> None:
        
        pathManager = PathManager()
        
        # Main menu image
        self.image_menu = pygame.image.load(pathManager.menu_image_path("menu_image.png"))
        self.image_menu = pygame.transform.scale(self.image_menu, resolution)
        
        # Start and options
        self.image_start = pygame.image.load(pathManager.menu_image_path("start-inactive.png"))
        self.image_options = pygame.image.load(pathManager.menu_image_path("options-inactive.png"))
        