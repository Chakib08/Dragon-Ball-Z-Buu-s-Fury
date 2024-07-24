import pygame
from typing import List
from pathmanager import PathManager

# Define a custom event for the arrow blitting
ARROW_BLIT_EVENT = pygame.USEREVENT + 1

class Menu:
    def __init__(self, resolution) -> None:
        # Initialize Pygame and set up the timer for the arrow blit event
        pygame.init()
        
        # Main menu image
        self.image_menu = pygame.image.load(PathManager.menu_image_path("menu_image_box.png"))
        self.image_menu = pygame.transform.scale(self.image_menu, resolution)
        
        # Start and options
        self.image_start = pygame.image.load(PathManager.menu_image_path("start-inactive.png"))
        self.image_options = pygame.image.load(PathManager.menu_image_path("options-inactive.png"))

        # Arrow selector image
        self.image_arrow = pygame.image.load(PathManager.menu_image_path("arrow.png"))
        self.image_arrow = pygame.transform.scale(self.image_arrow, (50, 50))
        
        self.isPlaying = False
        
        # Set the timer to trigger the event every second (1000 milliseconds)
        pygame.time.set_timer(ARROW_BLIT_EVENT, 500)
        
        # Arrow visibility flag and timestamp
        self.arrow_visible = False
        self.arrow_last_time = pygame.time.get_ticks()
        
    def launch_menu(self, screen: pygame.Surface, resolution: tuple, events: List[pygame.event.Event]) -> None:
        # Set up the start image rect
        image_start_rect = self.image_start.get_rect()
        image_start_rect.center = (680, resolution[1] / 1.5)

        image_options_rect = self.image_options.get_rect()
        image_options_rect.center = (680, resolution[1] / 1.35)
        
        image_arrow_rect = self.image_arrow.get_rect()
        #image_arrow_rect.center = (570, resolution[1] / 1.35)
        
        screen.blit(self.image_menu, (0, 0))
        screen.blit(self.image_start, image_start_rect.topleft)
        screen.blit(self.image_options, image_options_rect.topleft)
        
        # Manage arrow visibility
        current_time = pygame.time.get_ticks()
        if self.arrow_visible and current_time - self.arrow_last_time >= 200:
            self.arrow_visible = False
        
        # if self.arrow_visible:
        #     screen.blit(self.image_arrow, image_arrow_rect.topleft)
        
        for event in events:
            if event.type == pygame.MOUSEMOTION:
                if image_start_rect.collidepoint(event.pos):
                    self.image_start = pygame.image.load(PathManager.menu_image_path("start-active.png"))
                    if self.arrow_visible:
                        image_arrow_rect.center = (570, resolution[1] / 1.5)
                        screen.blit(self.image_arrow, image_arrow_rect.topleft)

                else:
                    self.image_start = pygame.image.load(PathManager.menu_image_path("start-inactive.png"))
                if image_options_rect.collidepoint(event.pos):
                    self.image_options = pygame.image.load(PathManager.menu_image_path("options-active.png"))
                    if self.arrow_visible:
                        image_arrow_rect.center = (570, resolution[1] / 1.35)
                        screen.blit(self.image_arrow, image_arrow_rect.topleft)

                else:
                    self.image_options = pygame.image.load(PathManager.menu_image_path("options-inactive.png"))
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if image_start_rect.collidepoint(event.pos):
                    self.isPlaying = True
            elif event.type == ARROW_BLIT_EVENT:
                self.arrow_visible = True
                self.arrow_last_time = current_time
