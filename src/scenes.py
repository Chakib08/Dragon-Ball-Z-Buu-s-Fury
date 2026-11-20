"""The screens the game shows, one at a time: the menu (with its character
and team screens), a story (arcade) fight, the online lobby and an online
match.

Each scene says what it does with a frame, which keys the controller's
buttons stand for on it, whether Escape opens the quit prompt there, and how
it lays itself out again when the screen changes size. The game (game.py)
owns what every scene shares: the display, the player's input, the quit
prompt and the menu itself; a new screen is a new Scene subclass registered
in SCENES.
"""

import pygame

from menu import State
from result_screen import ResultScreen

# What the controller's buttons stand for on each kind of screen (see
# gamepad.py): presses become the keys the screens already understand
# In a fight the controller is read as actions (controls.py); only Menu is a
# key, Escape, which pauses
FIGHT_KEYS = {"menu": pygame.K_ESCAPE}
MENU_KEYS = {"up": pygame.K_UP, "down": pygame.K_DOWN, "left": pygame.K_LEFT, "right": pygame.K_RIGHT,
             "a": pygame.K_RETURN, "menu": pygame.K_RETURN, "b": pygame.K_ESCAPE, "x": pygame.K_SPACE}
# X: new 1v1 room, RB: new team room, Y: refresh, A: join the first room
LOBBY_KEYS = {**MENU_KEYS, "a": pygame.K_1, "b": pygame.K_ESCAPE, "x": pygame.K_c, "rb": pygame.K_t,
              "y": pygame.K_r}
RESULT_KEYS = {"a": pygame.K_RETURN, "b": pygame.K_ESCAPE, "menu": pygame.K_RETURN}
# Pause (Quit / Main menu / No): no button quits by accident
PAUSE_KEYS = {"x": pygame.K_RETURN, "y": pygame.K_m, "b": pygame.K_ESCAPE, "menu": pygame.K_ESCAPE}


class Scene:
    name = None
    # A fight is on screen: the quit prompt offers "Main menu" too
    in_fight = False

    def __init__(self, game):
        self.game = game

    def gamepad_presses(self):
        """(button -> key map, buttons pressed this frame). Menus read the
        stick as a D-pad, with repeat."""
        return MENU_KEYS, self.game.gamepad.menu_presses()

    def escape_opens_prompt(self):
        """Whether Escape (or the back button) asks to quit here; elsewhere
        it means "back" and the scene handles it."""
        return False

    def frame(self, events, paused):
        """Handle this frame's events and draw."""
        raise NotImplementedError

    def resize(self, size):
        """The screen changed size: lay out what this scene owns."""


class MenuScene(Scene):
    name = "menu"

    def escape_opens_prompt(self):
        return self.game.menu.state == State.START

    def frame(self, events, paused):
        game = self.game
        game.menu.launch_menu(game.screen, game.resolution, events)
        if game.menu.isPlaying:
            if game.menu.online:
                game.open_lobby()
            else:
                game.start_story()


class StoryScene(Scene):
    """An arcade fight, then its result (retry or back to the menu)."""

    name = "story"
    in_fight = True

    def __init__(self, game):
        super().__init__(game)
        # The ResultScreen once the fight is over
        self.result = None

    def gamepad_presses(self):
        pressed = self.game.gamepad.pressed
        return (RESULT_KEYS if self.result is not None else FIGHT_KEYS), pressed

    def escape_opens_prompt(self):
        # On the result screen Esc means "main menu"
        return self.result is None

    def frame(self, events, paused):
        game = self.game
        if self.result is None:
            game.play_frame(events, paused)
            outcome = game.story_outcome()
            if outcome is not None:
                game.release_input()
                self.result = ResultScreen(game.resolution, victory=outcome == "victory")
            return
        # The fight is over: the world stays frozen behind the choice
        game.play_frame([], True)
        choice = None if paused else self.result.process(events)
        self.result.draw(game.screen)
        if choice == "retry":
            game.start_story()
        elif choice == "menu":
            game.back_to_menu()

    def resize(self, size):
        if self.result is not None:
            self.result.resize(size)


class LobbyScene(Scene):
    name = "lobby"

    def gamepad_presses(self):
        return LOBBY_KEYS, self.game.gamepad.menu_presses()

    def frame(self, events, paused):
        game = self.game
        action = game.lobby.update([] if paused else events)
        if action == "back":
            game.back_to_menu()
        elif isinstance(action, dict):
            game.start_match(action)
        else:
            game.lobby.draw(game.screen)

    def resize(self, size):
        game = self.game
        if game.lobby is not None:
            game.lobby.resize(size, game.menu.menu_image if game.menu is not None else None)


class OnlineScene(Scene):
    name = "online"
    in_fight = True

    def gamepad_presses(self):
        return FIGHT_KEYS, self.game.gamepad.pressed

    def escape_opens_prompt(self):
        return True

    def frame(self, events, paused):
        game = self.game
        # An online match never pauses: the opponent keeps playing
        game.match.handle_messages(game.net.poll())
        game.play_frame(events, False)
        game.match.after_frame()
        game.match.draw(game.screen)
        if game.match.finished:
            game.end_match()

    def resize(self, size):
        if self.game.match is not None:
            self.game.match.resize(size)


SCENES = (MenuScene, StoryScene, LobbyScene, OnlineScene)
