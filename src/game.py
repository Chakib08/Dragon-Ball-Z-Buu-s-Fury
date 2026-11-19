import os
from typing import List

import pygame

from animation import AnimationDirection, AnimationType
from constants import (
    C_RUN_ANIMATION_COUNT,
    C_WALK_ANIMATION_COUNT,
)
from dialog.dialogbox import DialogBox
from gamepad import Gamepad
from map import DEFAULT_ENEMY, MapManager
from npc import HEROES
from result_screen import ResultScreen
from menu import Menu, State
from net import NetClient
from online import LobbyScreen, OnlineMatch
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


def is_ios():
    # Set by the kivy-ios app that runs the game (see ios/)
    return os.environ.get("KIVY_BUILD") == "ios"


def is_mobile():
    """A phone or tablet: always full screen, drawn small and scaled up."""
    return is_android() or is_ios()


# On a phone (Android, iOS) the game draws at this height (and the screen's shape), and the
# GPU scales the picture up to the whole screen: drawing every pixel of a
# phone screen in Python is far too slow
ANDROID_RENDER_HEIGHT = 540


def android_render_size(screen_size):
    """Drawing size for a phone screen: landscape, ANDROID_RENDER_HEIGHT tall
    (or the screen's own size if that is smaller)."""
    width, height = max(screen_size), min(screen_size)
    if height <= ANDROID_RENDER_HEIGHT:
        return width, height
    return round(width * ANDROID_RENDER_HEIGHT / height), ANDROID_RENDER_HEIGHT


def create_display(window_size, fullscreen):
    """Open the game display.

    Fullscreen takes the whole screen at its native size (no borders, and on
    Android no system bars); the game lays itself out from the size it gets.
    Android is always fullscreen, drawn smaller and scaled up by the GPU.
    """
    if is_mobile():
        try:
            info = pygame.display.Info()
            size = android_render_size((info.current_w, info.current_h))
            return pygame.display.set_mode(size, pygame.FULLSCREEN | pygame.SCALED)
        except pygame.error:
            pass  # fall back to the native size below
    if fullscreen or is_mobile():
        try:
            screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
            if screen.get_width() > 0 and screen.get_height() > 0:
                return screen
        except pygame.error:
            pass
    return pygame.display.set_mode(window_size)


class Game:
    def __init__(self, resolution, caption, fullscreen=False):
        if is_ios():
            # Landscape only, like the Android app (read when SDL starts)
            os.environ.setdefault("SDL_IOS_ORIENTATIONS", "LandscapeLeft LandscapeRight")
        pygame.init()
        self.caption = caption
        self.isRunning = True
        pygame.display.set_caption(self.caption)
        # Size of the window when not full screen
        self.window_size = resolution
        self.screen = create_display(resolution, fullscreen)
        # Everything is laid out from the size the display really has
        self.resolution = self.screen.get_size()
        self.menu = None
        # menu, story, lobby or online (an online match)
        self.scene = "menu"
        self.net = NetClient()
        self.lobby = None
        self.match = None
        # Result of the story fight (ResultScreen) once it is over
        self.result = None

        self.music = None
        self.character = None
        self.map_manager = None
        self.select_character(DEFAULT_CHARACTER)

        self.dialogBox = DialogBox(self.resolution)
        # A game controller (the ROG Ally's controls, or any gamepad)
        self.gamepad = Gamepad()
        self.touch_controls = TouchControls(self.resolution)
        self.quit_prompt = QuitPrompt(self.resolution)
        # When the attack button was last pressed (None once it was used)
        self.attack_pressed_ms = None

    @property
    def is_fullscreen(self):
        return bool(self.screen.get_flags() & pygame.FULLSCREEN)

    def toggle_fullscreen(self):
        """Switch between full screen and a window.

        Changing mode gives a new display surface (often of another size).
        Everything that draws must use the new one: drawing into the old one
        crashes pygame, which is what pygame.display.toggle_fullscreen() led
        to because the game kept the surface it was given at start.
        """
        self.set_screen(create_display(self.window_size, not self.is_fullscreen))

    def set_screen(self, screen):
        """Use a new display surface and lay everything out for its size."""
        self.screen = screen
        self.resolution = screen.get_size()
        self.map_manager.set_screen(screen)
        # Rebuilt for the new size, keeping what is on screen right now
        dialog = self.dialogBox
        self.dialogBox = DialogBox(self.resolution)
        self.dialogBox.isBoxOpened = dialog.isBoxOpened
        self.dialogBox.texts = dialog.texts
        self.dialogBox.text_idx = dialog.text_idx
        self.dialogBox.letter_idx = dialog.letter_idx
        self.touch_controls = TouchControls(self.resolution)
        quit_prompt = self.quit_prompt
        self.quit_prompt = QuitPrompt(self.resolution)
        self.quit_prompt.is_open = quit_prompt.is_open
        if self.menu is not None:
            menu = Menu(self.resolution)
            menu.state = self.menu.state
            menu.isPlaying = self.menu.isPlaying
            menu.online = self.menu.online
            menu.selected_character = self.menu.selected_character
            menu.selected_allies = list(self.menu.selected_allies)
            menu.selected_enemies = list(self.menu.selected_enemies)
            self.menu = menu
        if self.lobby is not None:
            lobby = self.lobby
            lobby.screen_size = self.resolution
            lobby.background = self.menu.menu_image if self.menu is not None else None
        if self.match is not None:
            self.match._fonts(self.resolution)
        self.release_input()

    def select_character(self, name, enemies=(DEFAULT_ENEMY,), allies=()):
        """Start the world over with the given playable character, the
        enemies to fight and the allies fighting on his side."""
        if isinstance(enemies, str):
            enemies = (enemies,)
        self.character = Saiyan(*PLAYER_SPAWN, False, name)
        self.map_manager = MapManager(self.screen, self.character, enemies=enemies, allies=allies)

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

        # The analog stick wins over the controller, the controller over the
        # arrow keys
        gamepad = self.gamepad
        dx, dy = touch.stick_vector
        if not (dx or dy):
            dx, dy = gamepad.move_vector
        if not (dx or dy):
            dx = int(keys[pygame.K_RIGHT]) - int(keys[pygame.K_LEFT])
            dy = int(keys[pygame.K_DOWN]) - int(keys[pygame.K_UP])
        # Every one-shot button is consumed each frame, even if unused
        # Talking has no on-screen button for now (keyboard T only)
        interact_pressed = pygame.K_t in pressed_keys
        attack_pressed = touch.consume_action("attack") or pygame.K_a in pressed_keys
        super_pressed = touch.consume_action("super") or pygame.K_s in pressed_keys
        special_pressed = touch.consume_action("special") or pygame.K_d in pressed_keys
        # Choose the technique: arrows on top of the ki button, or Q / E
        combat = self.map_manager.combat
        if touch.consume_action("tech_prev") or pygame.K_q in pressed_keys:
            combat.cycle_technique(-1)
        if touch.consume_action("tech_next") or pygame.K_e in pressed_keys:
            combat.cycle_technique(1)
        # Choose the Super Saiyan level: arrows on top of the transform
        # button, or Z / X
        if touch.consume_action("form_prev") or pygame.K_z in pressed_keys:
            self.character.cycle_level(-1)
        if touch.consume_action("form_next") or pygame.K_x in pressed_keys:
            self.character.cycle_level(1)
        # One attack per press: holding the button does not repeat
        if attack_pressed:
            self.attack_pressed_ms = pygame.time.get_ticks()

        if interact_pressed:
            self.map_manager.check_npc_collisions(self.dialogBox)

        character = self.character
        guard_held = keys[pygame.K_f] or touch.blocking or "b" in gamepad.held
        # A charging technique goes off when its button is released
        if combat.charging and not (keys[pygame.K_d] or touch.special_held or "x" in gamepad.held):
            combat.release_charge()
        # Every hit plays the hurt animation, but acting cancels it: the
        # player is never stuck in a flinch
        if self.attack_requested or guard_held or super_pressed or special_pressed:
            character.cancel_hurt()
        # Attacking, hurt, transforming or firing a special: the animation
        # plays out first
        if character.update_action():
            character.stop_block()
            return
        if super_pressed:
            character.stop_block()
            character.transform()
        elif special_pressed:
            character.stop_block()
            self.map_manager.combat.start_special()
        if character.action is not None:
            return

        # Guard while the block button (or F) is held: no moving or attacking
        if guard_held and character.start_block():
            self.attack_pressed_ms = None
            return
        character.stop_block()

        if dx or dy:
            running = keys[pygame.K_SPACE] or touch.running or gamepad.running
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

    # The controller's presses as the keys the game already understands
    # (see gamepad.py): what a button does depends on what is on screen
    GAMEPAD_FIGHT_KEYS = {"a": pygame.K_a, "y": pygame.K_s, "x": pygame.K_d, "lb": pygame.K_q,
                          "rb": pygame.K_e, "rt": pygame.K_x, "view": pygame.K_t, "menu": pygame.K_ESCAPE}
    GAMEPAD_MENU_KEYS = {"up": pygame.K_UP, "down": pygame.K_DOWN, "left": pygame.K_LEFT, "right": pygame.K_RIGHT,
                         "a": pygame.K_RETURN, "menu": pygame.K_RETURN, "b": pygame.K_ESCAPE, "x": pygame.K_SPACE}
    GAMEPAD_LOBBY_KEYS = {"a": pygame.K_1, "b": pygame.K_ESCAPE, "x": pygame.K_c, "y": pygame.K_r}
    GAMEPAD_RESULT_KEYS = {"a": pygame.K_RETURN, "b": pygame.K_ESCAPE, "menu": pygame.K_RETURN}
    # Pause (Quit / Main menu / No): no button quits by accident
    GAMEPAD_PAUSE_KEYS = {"x": pygame.K_RETURN, "y": pygame.K_m, "b": pygame.K_ESCAPE, "menu": pygame.K_ESCAPE}

    def gamepad_key_events(self):
        """KEYDOWN events for the controller buttons pressed this frame."""
        gamepad = self.gamepad
        if not gamepad.connected:
            return []
        if self.quit_prompt.is_open:
            mapping, presses = self.GAMEPAD_PAUSE_KEYS, gamepad.pressed
        elif self.scene in ("story", "online") and self.result is not None:
            mapping, presses = self.GAMEPAD_RESULT_KEYS, gamepad.pressed
        elif self.scene in ("story", "online"):
            mapping, presses = self.GAMEPAD_FIGHT_KEYS, gamepad.pressed
        elif self.scene == "lobby":
            mapping, presses = {**self.GAMEPAD_MENU_KEYS, **self.GAMEPAD_LOBBY_KEYS}, gamepad.menu_presses()
        else:
            mapping, presses = self.GAMEPAD_MENU_KEYS, gamepad.menu_presses()
        return [pygame.event.Event(pygame.KEYDOWN, key=mapping[button], mod=0, unicode="", scancode=0,
                                   gamepad=True)
                for button in sorted(presses) if button in mapping]

    def release_input(self):
        """Drop every held button (transitions, knock-out, pause)."""
        self.touch_controls.clear()
        self.attack_pressed_ms = None
        if self.character is not None:
            self.character.stop_block()

    @property
    def attack_requested(self):
        return (
            self.attack_pressed_ms is not None
            and pygame.time.get_ticks() - self.attack_pressed_ms <= ATTACK_BUFFER_MS
        )

    # ---- Frame ------------------------------------------------------------------
    def update(self):
        self.map_manager.update(self.attack_requested and not self.character.blocking)
        if self.map_manager.combat.player_swung:
            self.attack_pressed_ms = None

    def draw(self):
        self.map_manager.draw()
        self.dialogBox.render(self.screen)
        self.map_manager.combat.draw(self.screen)
        technique = self.map_manager.combat.technique
        character = self.character
        levels = character.super_levels if hasattr(character, "super_levels") else []
        level = character.LEVEL_NAMES.get(character.target_level) if len(levels) > 1 else None
        self.touch_controls.draw(self.screen, technique.name if technique else None, level)

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

    # ---- Scenes -------------------------------------------------------------------
    def start_story(self):
        """Start (or restart, for Retry) the fight with the team chosen in
        the menu."""
        self.result = None
        self.release_input()
        self.select_character(self.menu.selected_character, tuple(self.menu.selected_enemies),
                              tuple(self.menu.selected_allies))
        self.play_music(self.map_manager.current_music)
        self.scene = "story"

    def open_lobby(self):
        self.menu.isPlaying = False
        self.menu.online = False
        self.lobby = LobbyScreen(
            self.net, self.resolution, self.menu.selected_character, self.menu.menu_image
        )
        self.scene = "lobby"

    def story_outcome(self):
        """"defeat" once the player's knock-out animation is over, "victory"
        once every enemy's is, else None."""
        if self.character.faint_finished:
            return "defeat"
        world = self.map_manager.maps.get("map")
        enemies = [npc for npc in (world.npcs if world else []) if npc.team != HEROES]
        if enemies and all(npc.faint_finished for npc in enemies):
            return "victory"
        return None

    def back_to_menu(self):
        self.result = None
        self.net.close()
        self.lobby = None
        self.match = None
        self.menu.isPlaying = False
        self.menu.online = False
        self.menu.state = State.START
        self.release_input()
        self.play_music(PathManager.soundtrack(MENU_MUSIC))
        self.scene = "menu"

    def start_match(self, start):
        self.release_input()
        self.match = OnlineMatch(self, self.net, start)
        self.play_music(self.map_manager.current_music)
        self.scene = "online"

    def end_match(self):
        self.net.send({"t": "leave"})
        self.match = None
        self.release_input()
        self.lobby.after_match()
        self.scene = "lobby"

    def frame(self, events, paused):
        """One frame of whichever scene is showing."""
        if self.scene == "menu":
            self.menu.launch_menu(self.screen, self.resolution, events)
            if self.menu.isPlaying:
                if self.menu.online:
                    self.open_lobby()
                else:
                    self.start_story()
        elif self.scene == "story":
            if self.result is None:
                self.play_frame(events, paused)
                outcome = self.story_outcome()
                if outcome is not None:
                    self.release_input()
                    self.result = ResultScreen(self.resolution, victory=outcome == "victory")
            else:
                # The fight is over: the world stays frozen behind the choice
                self.play_frame([], True)
                choice = None if paused else self.result.process(events)
                self.result.draw(self.screen)
                if choice == "retry":
                    self.start_story()
                elif choice == "menu":
                    self.back_to_menu()
        elif self.scene == "lobby":
            action = self.lobby.update([] if paused else events)
            if action == "back":
                self.back_to_menu()
            elif isinstance(action, dict):
                self.start_match(action)
            else:
                self.lobby.draw(self.screen)
        elif self.scene == "online":
            # An online match never pauses: the opponent keeps playing
            self.match.handle_messages(self.net.poll())
            self.play_frame(events, False)
            self.match.after_frame()
            self.match.draw(self.screen)
            if self.match.finished:
                self.end_match()

    def show_gamepad_hints(self):
        """While the controller is used: its buttons in the on-screen hints,
        and no touch buttons over the game."""
        active = self.gamepad.active
        self.touch_controls.hidden = active
        self.quit_prompt.gamepad_hints = active
        if self.menu is not None:
            self.menu.gamepad_hints = active
        if self.result is not None:
            self.result.gamepad_hints = active

    def loop_once(self, events):
        """One turn of the main loop: input (keyboard, touch, controller),
        the quit prompt, then the scene's frame."""
        for event in events:
            self.gamepad.handle_event(event)
        self.gamepad.update()
        events = list(events) + self.gamepad_key_events()
        self.show_gamepad_hints()
        # Quit button / Escape. Escape means "back" inside the menu's
        # sub-screens and the lobby, so it only asks to quit from the main
        # menu or while playing
        was_asking = self.quit_prompt.is_open
        playing = self.scene in ("story", "online")
        events = self.quit_prompt.process(
            events,
            # On the result screen Esc means "main menu"
            escape_opens=(playing and self.result is None)
            or (self.scene == "menu" and self.menu.state == State.START),
            menu_available=playing,
        )
        if self.quit_prompt.confirmed:
            self.isRunning = False
        if self.quit_prompt.to_menu:
            self.quit_prompt.to_menu = False
            if self.scene == "online":
                self.net.send({"t": "leave"})
            self.back_to_menu()
            events = []
        paused = was_asking or self.quit_prompt.is_open

        self.frame(events, paused)
        self.quit_prompt.draw(self.screen)

        for event in events:
            if event.type == pygame.QUIT:
                self.isRunning = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_F11 and not is_mobile():
                self.toggle_fullscreen()

    def run(self):
        clock = pygame.time.Clock()
        self.menu = Menu(self.resolution)
        self.play_music(PathManager.soundtrack(MENU_MUSIC))
        if getattr(self, "start_in", None) == "arcade":
            # Straight into a fight with the default team (build checks)
            self.menu.isPlaying = True

        while self.isRunning:
            self.loop_once(pygame.event.get())
            pygame.display.flip()
            clock.tick(Config.FPS)

        self.net.close()
        pygame.quit()
