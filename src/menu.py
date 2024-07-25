import pygame
from typing import List
from enum import Enum

from pathmanager import PathManager

# Define a custom event for the arrow blitting
ARROW_BLIT_EVENT = pygame.USEREVENT + 1

class State(Enum):
    START = 1
    OPTIONS = 2
    
class Menu:
    def __init__(self, resolution) -> None:
        # Initialize Pygame and set up the timer for the arrow blit event
        pygame.init()
        
        # Main menu image
        self.menu_image = pygame.image.load(PathManager.menu_image_path("menu_image_box.png"))
        self.menu_image = pygame.transform.scale(self.menu_image, resolution)
        
        # Start and options
        self.start_image = pygame.image.load(PathManager.menu_image_path("start-inactive.png"))
        self.options_image = pygame.image.load(PathManager.menu_image_path("options-inactive.png"))

        # Arrow selector image
        self.arrow_image = pygame.image.load(PathManager.menu_image_path("arrow.png"))
        self.arrow_image = pygame.transform.scale(self.arrow_image, (50, 50))
        
        self.isPlaying = False
        self.state = State.START
        
        # Set the timer to trigger the event every specific laps of time
        pygame.time.set_timer(ARROW_BLIT_EVENT, 500)
        
        # Arrow visibility flag and timestamp
        self.arrow_visible = False
        self.arrow_last_time = pygame.time.get_ticks()
        
    def launch_menu(self, screen: pygame.Surface, resolution: tuple, events: List[pygame.event.Event]) -> None:
        # Set up the start image rect
        image_start_rect = self.start_image.get_rect()
        image_start_rect.center = (680, resolution[1] / 1.5)

        image_options_rect = self.options_image.get_rect()
        image_options_rect.center = (680, resolution[1] / 1.35)
        
        image_arrow_rect = self.arrow_image.get_rect()
        
        screen.blit(self.menu_image, (0, 0))
        screen.blit(self.start_image, image_start_rect.topleft)
        screen.blit(self.options_image, image_options_rect.topleft)
        
        # Manage arrow visibility
        current_time = pygame.time.get_ticks()
        if self.arrow_visible and current_time - self.arrow_last_time >= 200:
            self.arrow_visible = False
            
        if self.state == State.START:
                self.start_image = pygame.image.load(PathManager.menu_image_path("start-active.png"))
                self.options_image = pygame.image.load(PathManager.menu_image_path("options-inactive.png"))
        elif self.state == State.OPTIONS:
            self.start_image = pygame.image.load(PathManager.menu_image_path("start-inactive.png"))
            self.options_image = pygame.image.load(PathManager.menu_image_path("options-active.png"))
            
        
        if self.arrow_visible:
            if self.state == State.START:
                image_arrow_rect.center = (590, resolution[1] / 1.5)
            elif self.state == State.OPTIONS:
                image_arrow_rect.center = (565, resolution[1] / 1.35)
            screen.blit(self.arrow_image, image_arrow_rect.topleft)
                
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_UP:
                    self.state = State.START
                if event.key == pygame.K_RETURN and self.state == State.START:
                    self.isPlaying = True   
                elif event.key == pygame.K_DOWN:
                    self.state = State.OPTIONS                                                 
            elif event.type == ARROW_BLIT_EVENT:
                self.arrow_visible = True
                self.arrow_last_time = current_time