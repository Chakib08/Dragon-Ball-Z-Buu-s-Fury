import os
from typing import List

import pygame

from animation import AnimationDirection, AnimationType
from constants import (
    C_RUN_ANIMATION_COUNT,
    C_WALK_ANIMATION_COUNT,
)
from dialog.dialogbox import DialogBox
from map import MapManager
from menu import Menu, State
from pathmanager import PathManager
from quit_prompt import QuitPrompt
from saiyan import Saiyan
from touch_controls import TouchControls
from utils.config import Config

PLAYER_SPAWN = (159, 289)
DEFAULT_CHARACTER = "goku"
# A press slightly before the attack is ready still counts, so mashing the
# button attacks as fast as the character can
ATTACK_BUFFER_MS = 250
MENU_MUSIC = "DBZ-Buus-Fury-Soundtrack-Theme"


def is_android():
    return "ANDROID_ARGUMENT" in os.environ


def create_display(window_size, fullscreen):
    """Open the game display.

    Fullscreen takes the whole screen at its native size (no borders, and on
    Android no system bars); the game lays itself out from the size it gets.
    Android is always fullscreen.
    """
    if fullscreen or is_android():
        try:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            if screen.get_width() > 0 and screen.get_height() > 0:
                return screen
        except pygame.error:
            pass
    return pygame.display.set_mode(window_size)


class Game:
    def __init__(self, resolution, caption, fullscreen=False):
        pygame.init()
        self.caption = caption
        self.isRunning = True
        pygame.display.set_caption(self.caption)
        self.screen = create_display(resolution, fullscreen)
        # Everything is laid out from the size the display really has
        self.resolution = self.screen.get_size()

        self.music = None
        self.character = None
        self.map_manager = None
        self.select_character(DEFAULT_CHARACTER)

        self.dialogBox = DialogBox(self.resolution)
        self.touch_controls = TouchControls(self.resolution)
        self.quit_prompt = QuitPrompt(self.resolution)
        # When the attack button was last pressed (None once it was used)
        self.attack_pressed_ms = None

    def select_character(self, name):
        """Start the world over with the given playable character."""
        self.character = Saiyan(*PLAYER_SPAWN, False, name)
        self.map_manager = MapManager(self.screen, self.character)

    def play_music(self, music):
        pygame.mixer.music.stop()
        self.music = music
        if self.isRunning:
            pygame.mixer.music.load(music)
            pygame.mixer.music.play(-1)  # Loop forever

    # ---- Input ------------------------------------------------------------------
    def handle_input(self, events: List[pygame.event.Event]):
        """Turn this frame's keyboard and touch input into player actions."""
        for event in events:
            self.touch_controls.handle_event(event)
        touch = self.touch_controls
        keys = pygame.key.get_pressed()
        pressed_keys = {event.key for event in events if event.type == pygame.KEYDOWN}

        directions = touch.directions
        dx = int(keys[pygame.K_RIGHT] or "right" in directions) - int(
            keys[pygame.K_LEFT] or "left" in directions
        )
        dy = int(keys[pygame.K_DOWN] or "down" in directions) - int(
            keys[pygame.K_UP] or "up" in directions
        )
        # Every one-shot button is consumed each frame, even if unused
        interact_pressed = touch.consume_action("interact") or pygame.K_t in pressed_keys
        attack_pressed = touch.consume_action("attack") or pygame.K_a in pressed_keys
        super_pressed = touch.consume_action("super") or pygame.K_s in pressed_keys
        special_pressed = touch.consume_action("special") or pygame.K_d in pressed_keys
        # One attack per press: holding the button does not repeat
        if attack_pressed:
            self.attack_pressed_ms = pygame.time.get_ticks()

        if interact_pressed:
            self.map_manager.check_npc_collisions(self.dialogBox)

        character = self.character
        # Attacking, hurt, transforming or firing a special: the animation
        # plays out first
        if character.update_action():
            return
        if super_pressed:
            character.transform()
        elif special_pressed:
            self.map_manager.combat.start_special()
        if character.action is not None:
            return

        if dx or dy:
            running = keys[pygame.K_SPACE] or touch.running
            animation = AnimationType.RUN.value if running else AnimationType.WALK.value
            count = C_RUN_ANIMATION_COUNT if running else C_WALK_ANIMATION_COUNT
            if abs(dx) > abs(dy):
                direction = AnimationDirection.RIGHT.value if dx > 0 else AnimationDirection.LEFT.value
            else:
                direction = AnimationDirection.DOWN.value if dy > 0 else AnimationDirection.UP.value
            character.move(f"{animation} {direction}", count, (dx, dy))
        else:
            character.save_location()
            character.face_idle()

    def release_input(self):
        """Drop every held button (transitions, knock-out, pause)."""
        self.touch_controls.clear()
        self.attack_pressed_ms = None

    @property
    def attack_requested(self):
        return (
            self.attack_pressed_ms is not None
            and pygame.time.get_ticks() - self.attack_pressed_ms <= ATTACK_BUFFER_MS
        )

    # ---- Frame ------------------------------------------------------------------
    def update(self):
        self.map_manager.update(self.attack_requested)
        if self.map_manager.combat.player_swung:
            self.attack_pressed_ms = None

    def draw(self):
        self.map_manager.draw()
        self.dialogBox.render(self.screen)
        self.map_manager.combat.draw(self.screen)
        self.touch_controls.draw(self.screen)

    def play_frame(self, events, paused):
        """One frame of gameplay. While paused the world is drawn but frozen."""
        can_act = self.map_manager.input_enabled and self.character.hp > 0
        if paused or not can_act:
            self.release_input()
        else:
            self.handle_input(events)
        if not paused:
            self.update()
        self.draw()
        if self.map_manager.isMusicChanged:
            self.play_music(self.map_manager.current_music)

    def run(self):
        clock = pygame.time.Clock()
        menu = Menu(self.resolution)
        self.play_music(PathManager.soundtrack(MENU_MUSIC))
        game_started = False

        while self.isRunning:
            events = pygame.event.get()
            # Quit button / Escape. Inside the menu's sub-screens Escape means
            # "back", so it only asks to quit from the main menu or the game
            was_asking = self.quit_prompt.is_open
            events = self.quit_prompt.process(
                events,
                escape_opens=menu.isPlaying or menu.state == State.START,
            )
            if self.quit_prompt.confirmed:
                self.isRunning = False
            paused = was_asking or self.quit_prompt.is_open

            if not menu.isPlaying:
                menu.launch_menu(self.screen, self.resolution, events)
            else:
                if not game_started:
                    if self.character.character_name != menu.selected_character:
                        self.select_character(menu.selected_character)
                    self.play_music(self.map_manager.current_music)
                    game_started = True
                self.play_frame(events, paused)
            self.quit_prompt.draw(self.screen)

            for event in events:
                if event.type == pygame.QUIT:
                    self.isRunning = False
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11 and not is_android():
                    pygame.display.toggle_fullscreen()

            pygame.display.flip()
            clock.tick(Config.FPS)

        pygame.quit()
