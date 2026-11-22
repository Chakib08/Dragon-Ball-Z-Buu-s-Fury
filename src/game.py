import os
from typing import List

import pygame

from animation import AnimationDirection, AnimationType
from constants import (
    C_RUN_ANIMATION_COUNT,
    C_WALK_ANIMATION_COUNT,
)
from dialog.dialogbox import DialogBox
from controls import Controls
from gamepad import Gamepad
import settings as user_settings
from map import DEFAULT_ENEMY, MapManager
from npc import HEROES
import epic
import sfx
import smoke
from menu import Menu, State
from net import NetClient
from online import LobbyScreen, OnlineMatch
from pathmanager import PathManager
from quit_prompt import QuitPrompt
from saiyan import Saiyan
from scenes import PAUSE_KEYS, SCENES
from touch_controls import TouchControls
from utils import timing
from utils.config import Config
from roster import level_name

PLAYER_SPAWN = (159, 289)
DEFAULT_CHARACTER = "goku"
# A press slightly before the attack is ready still counts, so mashing the
# button attacks as fast as the character can
ATTACK_BUFFER_MS = 250
# Unmei no Hi ~ Tamashii vs Tamashii (Gohan's SSJ2 theme)
MENU_MUSIC = "custom/unmei"


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
        # Kept here: the screen surface's own flags are not to be trusted once
        # the window changed size
        self.fullscreen = bool(self.screen.get_flags() & pygame.FULLSCREEN)
        # Everything is laid out from the size the display really has
        self.resolution = self.screen.get_size()
        # The real size of the window (on a phone the picture is drawn smaller
        # and scaled up, so this is not the surface's size)
        self.window_pixels = tuple(pygame.display.get_window_size())
        self.menu = None
        # The screens (see scenes.py), and the one showing
        self.scenes = {scene.name: scene(self) for scene in SCENES}
        self.current = self.scenes["menu"]
        self.net = NetClient()
        self.lobby = None
        self.match = None

        self.music = None
        self.character = None
        self.map_manager = None
        self.select_character(DEFAULT_CHARACTER)

        self.dialogBox = DialogBox(self.resolution)
        # A game controller (the ROG Ally's controls, or any gamepad)
        self.gamepad = Gamepad()
        # Which keys and buttons do what in a fight (the player may change
        # them in user_settings.json)
        self.controls = Controls(user_settings.load().get("controls"))
        self.touch_controls = TouchControls(self.resolution)
        self.quit_prompt = QuitPrompt(self.resolution)
        # When the attack button was last pressed (None once it was used)
        self.attack_pressed_ms = None

    # ---- Scenes (see scenes.py) ------------------------------------------------
    @property
    def scene(self):
        """The name of the screen showing: menu, story, lobby or online."""
        return self.current.name

    @scene.setter
    def scene(self, name):
        self.current = self.scenes[name]

    @property
    def result(self):
        """The story fight's result screen once it is over, else None."""
        return self.scenes["story"].result

    @result.setter
    def result(self, result):
        self.scenes["story"].result = result

    @property
    def is_fullscreen(self):
        return self.fullscreen

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
        self.fullscreen = bool(screen.get_flags() & pygame.FULLSCREEN)
        self.resolution = screen.get_size()
        self.window_pixels = tuple(pygame.display.get_window_size())
        self.map_manager.set_screen(screen)
        # Everything lays itself out again, keeping what it shows
        for part in (self.dialogBox, self.touch_controls, self.quit_prompt, self.menu):
            if part is not None:
                part.resize(self.resolution)
        for scene in self.scenes.values():
            scene.resize(self.resolution)
        self.release_input()

    def select_character(self, name, enemies=(DEFAULT_ENEMY,), allies=(), arena=None, epic=False):
        """Start the world over with the given playable character, the
        enemies to fight and the allies fighting on his side (epic: an Epic
        Fight's, up to 10 against 7)."""
        if isinstance(enemies, str):
            enemies = (enemies,)
        self.character = Saiyan(*PLAYER_SPAWN, False, name)
        self.map_manager = MapManager(self.screen, self.character, enemies=enemies, allies=allies,
                                      arena_name=arena, epic=epic)

    def play_music(self, music):
        pygame.mixer.music.stop()
        self.music = music
        if self.isRunning:
            pygame.mixer.music.load(music)
            pygame.mixer.music.play(-1)  # Loop forever

    # ---- Input ------------------------------------------------------------------
    def handle_input(self, events: List[pygame.event.Event]):
        """Turn this frame's keyboard, touch and controller input into player
        actions (see controls.py)."""
        for event in events:
            self.touch_controls.handle_event(event)
        intent = self.controls.read(events, self.touch_controls, self.gamepad)
        dx, dy = intent.move
        combat = self.map_manager.combat
        # Choose the technique (arrows on top of the ki button, or Q / E)
        # and the Super Saiyan level (arrows on top of the transform button)
        if "tech_prev" in intent:
            combat.cycle_technique(-1)
        if "tech_next" in intent:
            combat.cycle_technique(1)
        if "form_prev" in intent:
            self.character.cycle_level(-1)
        if "form_next" in intent:
            self.character.cycle_level(1)
        # One attack per press: holding the button does not repeat
        if "attack" in intent:
            self.attack_pressed_ms = pygame.time.get_ticks()
        if "talk" in intent:
            self.map_manager.check_npc_collisions(self.dialogBox)
        super_pressed = "super" in intent
        special_pressed = "special" in intent

        character = self.character
        guard_held = intent.holds("guard")
        # A charging technique goes off when its button is released
        if combat.charging and not intent.holds("special"):
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
            running = intent.holds("run")
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

    def gamepad_key_events(self):
        """KEYDOWN events for the controller buttons pressed this frame: what
        a button stands for depends on the screen (see scenes.py)."""
        gamepad = self.gamepad
        if not gamepad.connected:
            return []
        if self.quit_prompt.is_open:
            mapping, presses = PAUSE_KEYS, gamepad.pressed
        else:
            mapping, presses = self.current.gamepad_presses()
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
        level = None
        if len(levels) > 1:
            level = level_name(character.character_name, character.target_level,
                               character.LEVEL_NAMES.get(character.target_level))
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
        the menu (an Epic Fight's when one was chosen: its heroes' forms,
        its music, its enemies in waves)."""
        self.result = None
        self.release_input()
        fight = getattr(self.menu, "epic", None)
        if fight is not None:
            self.menu.selected_character = fight.hero
            self.menu.selected_allies = list(fight.allies)
            self.menu.selected_enemies = list(fight.waves[0])
            self.menu.selected_arena = fight.arena
        self.select_character(self.menu.selected_character, tuple(self.menu.selected_enemies),
                              tuple(self.menu.selected_allies), self.menu.selected_arena, epic=fight is not None)
        self.epic_wave = 0
        if fight is not None:
            epic.start_in_form(self.character, fight.form)
            for ally in self.map_manager.get_map().npcs:
                if ally.team == HEROES:
                    epic.start_in_form(ally, fight.ally_forms.get(ally.character_name))
                    epic.strengthen(ally, epic.ALLY_STRENGTH, health=False)
            enemies = [npc for npc in self.map_manager.get_map().npcs if npc.team != HEROES]
            for enemy in enemies:
                epic.strengthen(enemy, epic.ENEMY_STRENGTH)
            if enemies:
                epic.start_in_form(enemies[0], fight.boss_form)
            if fight.music:
                music = PathManager.soundtrack(fight.music)
                if os.path.exists(music):
                    self.map_manager.get_map().music = music
                    self.map_manager.current_music = music
        self.play_music(self.map_manager.current_music)
        self.scenes["story"].begin(fight)
        self.scene = "story"
        smoke.report("fight started")

    def next_wave(self):
        """An Epic Fight's next wave of enemies, if it has one (True)."""
        fight = getattr(self.menu, "epic", None)
        if fight is None or self.epic_wave + 1 >= len(fight.waves):
            return False
        self.epic_wave += 1
        for enemy in self.map_manager.add_enemies(fight.waves[self.epic_wave]):
            epic.strengthen(enemy, epic.ENEMY_STRENGTH)
        sfx.play("powerup")
        return True

    def open_lobby(self):
        self.menu.isPlaying = False
        self.menu.online = False
        self.lobby = LobbyScreen(
            self.net, self.resolution, self.menu.selected_character, self.menu.menu_image,
            name=self.menu.player_name, allies=self.menu.selected_allies, arena=self.menu.selected_arena,
            epic=self.menu.epic if self.menu.epic_online else None,
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
        self.menu.epic = None
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
        self.net.stop_udp()
        self.net.send({"t": "leave"})
        self.match = None
        self.release_input()
        self.lobby.after_match()
        self.scene = "lobby"

    def frame(self, events, paused):
        """One frame of whichever scene is showing."""
        self.current.frame(events, paused)

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

    def check_window_size(self, events):
        """The window got another size (a window manager adjusting a full
        screen window just after it opened, a phone turning): SDL replaced
        its pixels, so the screen surface the game holds must be replaced
        before anything is drawn (drawing into the old one crashes pygame).
        Returns True if it was."""
        if not any(event.type in (pygame.WINDOWSIZECHANGED, pygame.VIDEORESIZE) for event in events):
            return False
        # Compare with the window size we last laid out for. Never with the
        # surface size: on a phone the surface is smaller than the window, so
        # they always differ, and every resize event would rebuild the display.
        # Rebuilding fires new resize events, which rebuilt it again, and so on:
        # a new (black) frame every time = the screen blinking.
        if tuple(pygame.display.get_window_size()) == self.window_pixels:
            return False
        self.set_screen(create_display(self.window_size, self.fullscreen))
        # The events our own set_mode just queued are not news
        pygame.event.clear([pygame.WINDOWSIZECHANGED, pygame.WINDOWRESIZED, pygame.VIDEORESIZE])
        return True

    def loop_once(self, events):
        """One turn of the main loop: input (keyboard, touch, controller),
        the quit prompt, then the scene's frame."""
        self.check_window_size(events)
        for event in events:
            self.gamepad.handle_event(event)
        self.gamepad.update()
        events = list(events) + self.gamepad_key_events()
        self.show_gamepad_hints()
        # Quit button / Escape. Escape means "back" inside the menu's
        # sub-screens and the lobby, so it only asks to quit from the main
        # menu or while playing
        was_asking = self.quit_prompt.is_open
        events = self.quit_prompt.process(
            events,
            escape_opens=self.current.escape_opens_prompt(),
            menu_available=self.current.in_fight,
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
        self.menu = Menu(self.resolution, self.controls)
        self.play_music(PathManager.soundtrack(MENU_MUSIC))
        if getattr(self, "start_in", None) == "arcade":
            # Straight into a fight with the default team (build checks)
            self.menu.isPlaying = True

        while self.isRunning:
            self.loop_once(pygame.event.get())
            pygame.display.flip()
            # Speeds and animations follow the time this frame really took
            timing.advance(clock.tick(Config.FPS))

        self.net.close()
        pygame.quit()
