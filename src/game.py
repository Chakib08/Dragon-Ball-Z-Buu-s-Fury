import pygame
import pytmx
import pyscroll

from pathmanager import PathManager
from saiyan import Saiyan
from menu import Menu
from map import MapManager

#TODO : Remove Global variables

# Define all constants here
walk_animation_nbr = 4
transform_ssj_nbr = 12

pathManager = PathManager()
goku_base_json_file = pathManager.character_json_path("goku")
#goku_ssj_sprite_path = current_dir.parent / "Graphics/assets/Goku/GokuSS1.png"


class Game:
    def __init__(self, resolution, caption):
        # Initialize game window
        self.resolution = resolution
        self.caption = caption
        self.screen = self.set_mode()

        # Intancite Goku character
        self.character = Saiyan(240, 345, False, goku_base_json_file)
        
        # Manage map
        self.map_manager = MapManager(self.screen, self.character)


    def set_mode(self):
        return pygame.display.set_mode(self.resolution)

    def set_caption(self):
        pygame.display.set_caption(self.caption)

    def play_music(self, music):
        # Load the sound file
        pygame.mixer.music.stop()
        self.isRunning = True
        self.music = music
        pygame.mixer.music.load(self.music)
        # Play the sound
        if (self.isRunning):
            pygame.mixer.music.play(-1)  # Play music indefinitely
        else:
            pygame.mixer.music.stop()

    def keyBoard_input(self):
        isPressed = pygame.key.get_pressed()

        if isPressed[pygame.K_UP]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Up", walk_animation_nbr)
            else:
                self.character.animate("Walk Up", walk_animation_nbr)
        elif isPressed[pygame.K_DOWN]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Down", walk_animation_nbr)
            else:
                self.character.animate("Walk Down", walk_animation_nbr)
        elif isPressed[pygame.K_RIGHT]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Right", walk_animation_nbr)
            else:
                self.character.animate("Walk Right", walk_animation_nbr)
        elif isPressed[pygame.K_LEFT]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Left", walk_animation_nbr)
            else:
                self.character.animate("Walk Left", walk_animation_nbr)
        else:
            self.character.images = []  # Reset the animation frames
            self.character.current_animation_index = 0
            # self.character.sprit_sheet = pygame.image.load(
            #     current_dir.parent / "Graphics/assets/Goku/goku.png")

            if self.character.isTransofrmed == False:
                if "Down" in self.character.animation_name:
                    self.character.image = self.character.get_image_by_animation_name(
                        "IDLE Down")
                elif "Right" in self.character.animation_name:
                    self.character.image = self.character.get_image_by_animation_name(
                        "IDLE Right")
                elif "Left" in self.character.animation_name:
                    self.character.image = self.character.get_image_by_animation_name(
                        "IDLE Left")
                    self.character.image = pygame.transform.flip(
                        self.character.image, True, False)
                else:
                    self.character.image = self.character.get_image_by_animation_name(
                        "IDLE Up")


    def update(self):
        self.map_manager.update()

    def run(self):
        main_theme = pathManager.soundtrack("DBZ-Buus-Fury-Soundtrack-Theme")
        goku_home_theme = pathManager.soundtrack("DBZ-Buus-Fury-Soundtrack-Gokus-Home")
        self.play_music(main_theme)
        clock = pygame.time.Clock()
        self.music_changed = True

        # Initialize Menu
        mainMenu = Menu(self.resolution)

        # Set up the start image rect
        image_start_rect = mainMenu.image_start.get_rect()
        image_start_rect.center = (
            self.resolution[0] / 2, self.resolution[1] / 1.5)

        image_options_rect = mainMenu.image_options.get_rect()
        image_options_rect.center = (
            self.resolution[0] / 2, self.resolution[1] / 1.42)

        self.isPlaying = False

        while self.isRunning:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.isRunning = False
                elif event.type == pygame.MOUSEMOTION:
                    if image_start_rect.collidepoint(event.pos):
                        mainMenu.image_start = pygame.image.load(pathManager.menu_image_path("start-active.png"))
                    else:
                        mainMenu.image_start = pygame.image.load(pathManager.menu_image_path("start-inactive.png"))
                    if image_options_rect.collidepoint(event.pos):
                        mainMenu.image_options =  pygame.image.load(pathManager.menu_image_path("options-active.png"))
                    else:
                        mainMenu.image_options = pygame.image.load(pathManager.menu_image_path("options-inactive.png"))
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if image_start_rect.collidepoint(event.pos):
                        self.isPlaying = True

            # Update game state and draw
            if self.isPlaying:
                if self.music_changed:
                    self.play_music(goku_home_theme)
                    self.music_changed = False
                self.character.save_location()
                if self.map_manager.input_enabled:
                    self.keyBoard_input()
                self.update()
                self.map_manager.draw()
            else:
                self.screen.blit(mainMenu.image_menu, (0, 0))
                self.screen.blit(mainMenu.image_start,
                                 image_start_rect.topleft)
                self.screen.blit(mainMenu.image_options,
                                 image_options_rect.topleft)

            # Update the display
            pygame.display.flip()

            # Cap the frame rate
            clock.tick(60)

        pygame.quit()
