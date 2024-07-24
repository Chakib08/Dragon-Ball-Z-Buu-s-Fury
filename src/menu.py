import pygame
from typing import List

from pathmanager import PathManager

class Menu:
    def __init__(self, resolution) -> None:        
        # Main menu image
        self.image_menu = pygame.image.load(PathManager.menu_image_path("menu_image_box.png"))
        self.image_menu = pygame.transform.scale(self.image_menu, resolution)
        
        # Start and options
        self.image_start = pygame.image.load(PathManager.menu_image_path("start-inactive.png"))
        self.image_options = pygame.image.load(PathManager.menu_image_path("options-inactive.png"))
        
        self.isPlaying = False
        
    def launch_menu(self, screen: pygame.Surface, resolution: tuple, events: List[pygame.event.Event]) -> None:
        # Set up the start image rect
        image_start_rect = self.image_start.get_rect()
        image_start_rect.center = (
            resolution[0] / 2, resolution[1] / 1.5)

        image_options_rect = self.image_options.get_rect()
        image_options_rect.center = (
            resolution[0] / 2, resolution[1] / 1.42)
        
        screen.blit(self.image_menu, (0, 0))
        screen.blit(self.image_start, image_start_rect.topleft)
        screen.blit(self.image_options, image_options_rect.topleft)
        
        for event in events:
            if event.type == pygame.MOUSEMOTION:
                if image_start_rect.collidepoint(event.pos):
                    self.image_start = pygame.image.load(PathManager.menu_image_path("start-active.png"))
                else:
                    self.image_start = pygame.image.load(PathManager.menu_image_path("start-inactive.png"))
                if image_options_rect.collidepoint(event.pos):
                    self.image_options =  pygame.image.load(PathManager.menu_image_path("options-active.png"))
                else:
                    self.image_options = pygame.image.load(PathManager.menu_image_path("options-inactive.png"))
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if image_start_rect.collidepoint(event.pos):
                    self.isPlaying = True    