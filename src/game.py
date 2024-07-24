import pygame
import pytmx
import pyscroll

from pathmanager import PathManager
from saiyan import Saiyan
from menu import Menu
from map import MapManager
from dialog.dialogbox import DialogBox
from utils.config import Config

#TODO : Remove Global variables

# Define all constants here
walk_animation_nbr = 4
transform_ssj_nbr = 12

class Game:
    def __init__(self, resolution, caption):
        # Initialize game
        pygame.init() 
        self.resolution = resolution
        self.caption = caption
        self.isRunning = True
        pygame.display.set_caption(self.caption)
        self.screen = pygame.display.set_mode(self.resolution)
        
        # Intanciate Goku character
        self.character = Saiyan(159, 289, False, "goku")
        
        # Manage map
        self.map_manager = MapManager(self.screen, self.character)
        
        # Create dialog box
        self.dialogBox = DialogBox()        

    def play_music(self, music):
        # Load the sound file
        pygame.mixer.music.stop()
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
        # Init clock and other attributes
        onlyOnce = True
        clock = pygame.time.Clock()
        fps = Config.FPS

        # Initialize Menu
        mainMenu = Menu(self.resolution)
        # Play main theme        
        self.play_music(PathManager.soundtrack("DBZ-Buus-Fury-Soundtrack-Theme"))

        while self.isRunning:
            # Get all the pygame events
            events = pygame.event.get()
            # Launch main menu
            if not mainMenu.isPlaying:
                mainMenu.launch_menu(self.screen, self.resolution, events)
            # Start the game
            else:
                for event in events:
                    if event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_t:
                            self.map_manager.check_npc_collisions(self.dialogBox)
                if(onlyOnce):
                    self.play_music(self.map_manager.current_music)
                    onlyOnce = False
                # Update game state and draw map groups
                self.update()
                self.map_manager.draw()
                self.dialogBox.render(self.screen)
                if self.map_manager.isMusicChanged:
                    self.play_music(self.map_manager.current_music)
                self.character.save_location()
                if self.map_manager.input_enabled:
                    self.keyBoard_input()

            # Common events
            for event in events:
                if event.type == pygame.QUIT:
                    self.isRunning = False
            # Update the display
            pygame.display.flip()
            # Cap the frame rate
            clock.tick(fps)

        pygame.quit()
