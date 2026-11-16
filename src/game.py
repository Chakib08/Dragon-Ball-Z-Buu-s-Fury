import pygame
import pytmx
import pyscroll
from typing import List

from pathmanager import PathManager
from saiyan import Saiyan
from menu import Menu
from map import MapManager
from dialog.dialogbox import DialogBox
from utils.config import Config
from constants import *
from animation import AnimationType, AnimationDirection
from touch_controls import TouchControls

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
        self.touch_controls = TouchControls(self.resolution)
        self.attack_held = False

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
    

    def keyBoard_input(self, events: List[pygame.event.Event]):
        for event in events:
            self.touch_controls.handle_event(event)

        is_pressed = pygame.key.get_pressed()
        touch_directions = self.touch_controls.directions
        dx = int(is_pressed[pygame.K_RIGHT] or "right" in touch_directions) - int(
            is_pressed[pygame.K_LEFT] or "left" in touch_directions
        )
        dy = int(is_pressed[pygame.K_DOWN] or "down" in touch_directions) - int(
            is_pressed[pygame.K_UP] or "up" in touch_directions
        )
        interact_pressed = self.touch_controls.consume_action("interact")
        attack_pressed = self.touch_controls.consume_action("attack")
        self.attack_held = (
            is_pressed[pygame.K_a]
            or self.touch_controls.attacking
            or attack_pressed
        )

        pressed_keys = {event.key for event in events if event.type == pygame.KEYDOWN}
        super_pressed = self.touch_controls.consume_action("super") or pygame.K_s in pressed_keys
        special_pressed = self.touch_controls.consume_action("special") or pygame.K_d in pressed_keys

        if pygame.K_t in pressed_keys or interact_pressed:
            self.map_manager.check_npc_collisions(self.dialogBox)

        # Hurt, transforming or firing a special: the animation plays out first
        if self.character.update_action():
            self.attack_held = False
            return
        if super_pressed:
            self.character.transform()
        elif special_pressed:
            self.map_manager.combat.start_special()
        if self.character.action is not None:
            self.attack_held = False
            return

        if self.attack_held:
            attack_animation = {
                AnimationDirection.UP.value: C_ATTACK_UP,
                AnimationDirection.DOWN.value: C_ATTACK_DOWN,
                AnimationDirection.LEFT.value: C_ATTACK_LEFT,
                AnimationDirection.RIGHT.value: C_ATTACK_RIGHT,
            }[self.character.facing]
            self.character.attack(attack_animation, C_ATTACK_ANIMATION_COUNT)

        if (dx or dy) and not self.attack_held:
            running = is_pressed[pygame.K_SPACE] or self.touch_controls.running
            animation = AnimationType.RUN.value if running else AnimationType.WALK.value
            count = C_RUN_ANIMATION_COUNT if running else C_WALK_ANIMATION_COUNT
            if abs(dx) > abs(dy):
                direction = AnimationDirection.RIGHT.value if dx > 0 else AnimationDirection.LEFT.value
            else:
                direction = AnimationDirection.DOWN.value if dy > 0 else AnimationDirection.UP.value
            self.character.move(f"{animation} {direction}", count, (dx, dy))
        elif not self.attack_held:
            self.character.images = []  # Reset the animation frames
            self.character.current_animation_macro = None
            self.character.current_animation_index = 0
            self.character.clock = 0
            self.character.save_location()
            if AnimationDirection.DOWN.value in self.character.animation_name:
                self.character.image = self.character.get_image_by_animation_name(C_IDLE_DOWN)
            elif AnimationDirection.RIGHT.value in self.character.animation_name:
                self.character.image = self.character.get_image_by_animation_name(C_IDLE_RIGHT)
            elif AnimationDirection.LEFT.value in self.character.animation_name:
                self.character.image = self.character.get_image_by_animation_name(C_IDLE_LEFT)
                self.character.image = pygame.transform.flip(self.character.image, True, False)
            else:
                self.character.image = self.character.get_image_by_animation_name(C_IDLE_UP)

    def update(self):
        self.map_manager.update(self.attack_held)

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
                if self.character.character_name != mainMenu.selected_character:
                    self.character = Saiyan(159, 289, False, mainMenu.selected_character)
                    self.map_manager = MapManager(self.screen, self.character)
                if(onlyOnce):
                    self.play_music(self.map_manager.current_music)
                    onlyOnce = False
                if self.map_manager.input_enabled and self.character.hp > 0:
                    self.keyBoard_input(events)
                else:
                    self.touch_controls.clear()
                    self.attack_held = False
                # Update game state and draw map groups
                self.update()
                self.map_manager.draw()
                self.dialogBox.render(self.screen)
                self.map_manager.combat.draw(self.screen)
                self.touch_controls.draw(self.screen)
                if self.map_manager.isMusicChanged:
                    self.play_music(self.map_manager.current_music)

            # Common events
            for event in events:
                if event.type == pygame.QUIT:
                    self.isRunning = False
            # Update the display
            pygame.display.flip()
            # Cap the frame rate
            clock.tick(fps)

        pygame.quit()
