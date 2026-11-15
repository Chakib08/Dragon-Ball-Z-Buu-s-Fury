import pygame
from typing import List
from enum import Enum

from pathmanager import PathManager

# Define a custom event for the arrow blitting
ARROW_BLIT_EVENT = pygame.USEREVENT + 1

class State(Enum):
    START = 1
    OPTIONS = 2

# TODO: Remove magic numbers, retreive the latters from the app config
class Menu:
    def __init__(self, resolution) -> None:
        # Main menu image
        self.menu_image = pygame.image.load(PathManager.menu_image_path("menu_image_box.png"))
        self.menu_image = pygame.transform.scale(self.menu_image, resolution)
        
        # Start and options
        self.menu_images = {
            State.START: {
                False: pygame.image.load(PathManager.menu_image_path("start-inactive.png")),
                True: pygame.image.load(PathManager.menu_image_path("start-active.png")),
            },
            State.OPTIONS: {
                False: pygame.image.load(PathManager.menu_image_path("options-inactive.png")),
                True: pygame.image.load(PathManager.menu_image_path("options-active.png")),
            },
        }
        self.start_image = self.menu_images[State.START][False]
        self.options_image = self.menu_images[State.OPTIONS][False]
        self.options_font = pygame.font.Font(None, 42)
        self.options_title_font = pygame.font.Font(None, 58)

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
        image_start_rect.center = (resolution[0] - 520, resolution[1] / 1.5)
        # Set up the options image rect
        image_options_rect = self.options_image.get_rect()
        image_options_rect.center = (resolution[0] - 520, resolution[1] / 1.35)
        # Set up the arrow image rect
        image_arrow_rect = self.arrow_image.get_rect()
        if self.state == State.OPTIONS:
            self._draw_options(screen, resolution)
            for event in events:
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    self.state = State.START
                elif self._is_tap(event, resolution):
                    self.state = State.START
            return

        self.start_image = self.menu_images[State.START][self.state == State.START]
        self.options_image = self.menu_images[State.OPTIONS][self.state == State.OPTIONS]

        # Blit images
        screen.blit(self.menu_image, (0, 0))
        screen.blit(self.start_image, image_start_rect.topleft)
        screen.blit(self.options_image, image_options_rect.topleft)
        
        # Manage arrow visibility
        current_time = pygame.time.get_ticks()
        if self.arrow_visible and current_time - self.arrow_last_time >= 200:
            self.arrow_visible = False
        
        # Blit the arrow image according to the selected state
        if self.arrow_visible:
            if self.state == State.START:
                image_arrow_rect.center = (590, resolution[1] / 1.5)
            elif self.state == State.OPTIONS:
                image_arrow_rect.center = (565, resolution[1] / 1.35)
            screen.blit(self.arrow_image, image_arrow_rect.topleft)
        # Handle keyboard and touch selection.
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.state = State.START
                if event.key == pygame.K_RETURN and self.state == State.START:
                    self.isPlaying = True   
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.state = State.OPTIONS                                                 
            elif event.type == ARROW_BLIT_EVENT:
                self.arrow_visible = True
                self.arrow_last_time = current_time
            elif self._is_tap(event, resolution):
                position = self._event_position(event, resolution)
                if image_start_rect.collidepoint(position):
                    self.state = State.START
                    self.isPlaying = True
                elif image_options_rect.collidepoint(position):
                    self.state = State.OPTIONS

    def _draw_options(self, screen, resolution):
        screen.blit(self.menu_image, (0, 0))
        lines = [
            "Controls",
            "Move: Arrow keys or on-screen D-pad",
            "Run: Hold Space or the R button",
            "Attack: A key or the A button",
            "Talk: T key or the T button",
            "Press Esc or tap to return",
        ]
        y = resolution[1] * 0.30
        for index, line in enumerate(lines):
            font = self.options_title_font if index == 0 else self.options_font
            color = (255, 230, 120) if index == 0 else (255, 255, 255)
            text = font.render(line, True, color)
            screen.blit(text, text.get_rect(center=(resolution[0] / 2, y)))
            y += 68 if index == 0 else 52

    @staticmethod
    def _is_tap(event, resolution):
        return (
            event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        ) or event.type == pygame.FINGERDOWN

    @staticmethod
    def _event_position(event, resolution):
        if event.type == pygame.FINGERDOWN:
            return event.x * resolution[0], event.y * resolution[1]
        return event.pos