import json
import pygame
from typing import List
from enum import Enum

from pathmanager import PathManager
from animation import Animator
from controls import Controls
from difficulty import enemy_profile
from taps import tap_position
from version import __version__
from map import MAX_ALLIES, MAX_ENEMIES
from portraits import portrait
from stats import character_stats
import settings as user_settings
import roster

GAME_TITLE = "DRAGON BALL Z"
GAME_SUBTITLE = "TRUNKS HOPE"
DEVELOPER = "Developed by Chakib08"
BACKGROUND_IMAGE = "dbz-game-menu.jpg"

class State(Enum):
    START = 1
    OPTIONS = 2
    CHARACTER_SELECT = 3
    ENEMY_SELECT = 4
    ALLY_SELECT = 5
    # Online: the player's name, before the character
    NAME_ENTRY = 6

class Menu:
    # The main menu's entries: id, label, and the line shown under the list
    # while the entry is highlighted
    MAIN_ITEMS = (
        ("story", "Story Mode", "The story of Trunks' hope (coming soon)"),
        ("arcade", "Arcade Mode", "Pick your team and fight: from 1v1 up to 4v4"),
        ("online", "Online Mode", "1v1 against another player on a lobby server"),
        ("options", "Options", "Controls and settings"),
    )
    GOLD = (255, 205, 60)
    NAME_LENGTH = 16
    NOTICE_MS = 2600
    # Show the controller's buttons in the hints (set by the game)
    gamepad_hints = False

    def __init__(self, resolution, controls=None) -> None:
        # The fight's keys and buttons, for the control guide
        self.controls = controls if controls is not None else Controls()
        self._artwork = pygame.image.load(PathManager.menu_image_path(BACKGROUND_IMAGE))
        # Highlighted entry (Arcade: the one most players want)
        self.selected_item = 1
        # "Not available yet" message (Story mode) until this time
        self.notice_until = 0
        self.isPlaying = False
        # True when the character was chosen for an online match
        self.online = False
        self.state = State.START
        # Every character whose sheets are installed (Config/roster.json)
        self.character_names = roster.characters()
        self.selected_character = "goku"
        # The name other players see online (saved between sessions)
        self.player_name = str(user_settings.load().get("player_name") or "")[:self.NAME_LENGTH]
        self.name_ok_rect = None
        self.name_field_rect = None
        # The team of the story mode, chosen after the character: his allies
        # (none to fight alone) and the enemies (at least one)
        self.selected_allies = []
        self.selected_enemies = ["gohan"]
        # Card the keyboard is on, in the ally and enemy screens
        self.focus = 0
        self.continue_rect = None
        self.back_rect = None
        self.button_font = pygame.font.Font(None, 40)
        self.enemy_difficulties = {name: enemy_profile(name).difficulty for name in self.character_names}
        self.difficulty_font = pygame.font.Font(None, 32)
        self.character_font = pygame.font.Font(None, 42)
        self.character_title_font = pygame.font.Font(None, 58)
        self.character_previews = {}
        self.character_rects = {}
        for character_name in self.character_names:
            preview = Animator(character_name).image
            self.character_previews[character_name] = pygame.transform.scale(
                preview, (preview.get_width() * 4, preview.get_height() * 4)
            )
        self.resize(resolution)

    def resize(self, resolution):
        """Lay the menu out for this screen size; where the player is in it
        (screen, choices) stays."""
        self.resolution = resolution
        artwork = self._artwork
        # The artwork fills the screen without being stretched
        self.background = self._cover(artwork, resolution)
        # Behind the other screens (characters, options, lobby): darker, so
        # their cards and text stand out
        self.menu_image = self.background.copy()
        shade = pygame.Surface(resolution, pygame.SRCALPHA)
        shade.fill((8, 10, 20, 150))
        self.menu_image.blit(shade, (0, 0))
        # Main menu: dark on the left, where the title and entries are
        self.main_image = self.background.copy()
        self.main_image.blit(self._left_gradient(resolution), (0, 0))
        self._layout_main(resolution)

        # The control guide must fit on any screen height
        self.options_font_size = max(20, min(42, int(resolution[1] / 25)))
        self.options_font = pygame.font.Font(None, self.options_font_size)
        self.options_title_font = pygame.font.Font(None, int(self.options_font_size * 1.4))
        # Previews scaled to the cards of this screen size
        self._fitted_previews = {}
        self._version_label = None
        

    def launch_menu(self, screen: pygame.Surface, resolution: tuple, events: List[pygame.event.Event]) -> None:
        if self.state == State.NAME_ENTRY:
            self._draw_name_entry(screen, resolution)
            for event in events:
                if event.type == pygame.TEXTINPUT:
                    typed = "".join(ch for ch in event.text if ch.isprintable())
                    self.player_name = (self.player_name + typed)[:self.NAME_LENGTH]
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_BACKSPACE:
                        self.player_name = self.player_name[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        self.confirm_name()
                    elif event.key in (pygame.K_ESCAPE, pygame.K_AC_BACK):
                        self.go_back()
                elif self._is_tap(event, resolution):
                    position = self._event_position(event, resolution)
                    if self.back_rect is not None and self.back_rect.collidepoint(position):
                        self.go_back()
                    elif self.name_ok_rect is not None and self.name_ok_rect.collidepoint(position):
                        self.confirm_name()
                    elif self.name_field_rect is not None and self.name_field_rect.collidepoint(position):
                        pygame.key.start_text_input()  # the phone's keyboard again
                if self.state != State.NAME_ENTRY:
                    break
            return

        if self.state == State.OPTIONS:
            self._draw_options(screen, resolution)
            for event in events:
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    self.state = State.START
                elif self._is_tap(event, resolution):
                    self.state = State.START
            return

        if self.state in self.PICKING:
            picking = self.PICKING[self.state]
            self._draw_character_select(screen, resolution, picking)
            state = self.state
            for event in events:
                self._select_event(event, resolution, picking)
                # The screen changed (Back, Next, Fight!): the rest is not for it
                if self.isPlaying or self.state != state:
                    break
            return

        self._draw_main(screen, resolution)
        for event in events:
            if self.notice_until and (event.type == pygame.KEYDOWN or self._is_tap(event, resolution)):
                self.notice_until = 0  # any key or tap closes the message
                continue
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.selected_item = (self.selected_item - 1) % len(self.MAIN_ITEMS)
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.selected_item = (self.selected_item + 1) % len(self.MAIN_ITEMS)
                elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                    self.choose(self.MAIN_ITEMS[self.selected_item][0])
                elif event.key == pygame.K_o:
                    self.choose("online")
            elif event.type == pygame.MOUSEMOTION and not getattr(event, "touch", False):
                item = self._item_at(event.pos)
                if item is not None:
                    self.selected_item = item  # the mouse highlights what it points at
            elif self._is_tap(event, resolution):
                item = self._item_at(self._event_position(event, resolution))
                if item is not None:
                    self.selected_item = item
                    self.choose(self.MAIN_ITEMS[item][0])
            if self.state != State.START:
                break

    # ---- Main menu ----------------------------------------------------------------
    def choose(self, item):
        """Open a main menu entry."""
        if item == "story":
            # Not there yet: say so instead of doing nothing
            self.notice_until = pygame.time.get_ticks() + self.NOTICE_MS
        elif item == "arcade":
            self.online = False
            self.state = State.CHARACTER_SELECT
        elif item == "online":
            self.open_online()
        elif item == "options":
            self.state = State.OPTIONS

    @property
    def notice_shown(self):
        return self.notice_until and pygame.time.get_ticks() < self.notice_until

    def _item_at(self, position):
        for index, (item, _, _) in enumerate(self.MAIN_ITEMS):
            if self.item_rects[item].collidepoint(position):
                return index
        return None

    @staticmethod
    def _cover(image, size):
        """image scaled to fill size, keeping its shape: what is too much is
        cut off (more from the bottom than the top, where the faces are)."""
        scale = max(size[0] / image.get_width(), size[1] / image.get_height())
        scaled = pygame.transform.smoothscale(
            image.convert() if pygame.display.get_surface() else image,
            (max(size[0], round(image.get_width() * scale)), max(size[1], round(image.get_height() * scale))))
        x = (scaled.get_width() - size[0]) // 2
        y = int((scaled.get_height() - size[1]) * 0.3)
        return scaled.subsurface((x, y, size[0], size[1])).copy()

    @staticmethod
    def _left_gradient(size):
        """Dark on the left, fading out by the middle of the screen."""
        gradient = pygame.Surface(size, pygame.SRCALPHA)
        fade_end = int(size[0] * 0.6)
        for x in range(fade_end):
            alpha = int(225 * (1 - x / fade_end) ** 1.3)
            pygame.draw.line(gradient, (6, 8, 18, alpha), (x, 0), (x, size[1]))
        return gradient

    @staticmethod
    def _outlined(font, text, color, outline=(10, 10, 20), width=2):
        """Text with a dark outline: reads over any part of the artwork."""
        inner = font.render(text, True, color)
        edge = font.render(text, True, outline)
        surface = pygame.Surface((inner.get_width() + 2 * width, inner.get_height() + 2 * width), pygame.SRCALPHA)
        for dx in range(-width, width + 1):
            for dy in range(-width, width + 1):
                if dx or dy:
                    surface.blit(edge, (width + dx, width + dy))
        surface.blit(inner, (width, width))
        return surface

    def _layout_main(self, resolution):
        """Fonts, the pre-drawn texts and where every entry goes."""
        width, height = resolution
        self.main_left = int(width * 0.06)
        title_font = pygame.font.Font(None, max(36, int(height * 0.085)))
        subtitle_font = pygame.font.Font(None, max(44, int(height * 0.12)))
        item_font = pygame.font.Font(None, max(30, int(height * 0.07)))
        self.description_font = pygame.font.Font(None, max(20, int(height * 0.04)))
        small_font = pygame.font.Font(None, max(20, int(height * 0.036)))

        self.title_label = self._outlined(title_font, GAME_TITLE, (255, 255, 255))
        self.subtitle_label = self._outlined(subtitle_font, GAME_SUBTITLE, self.GOLD, width=3)
        self.title_top = int(height * 0.07)
        items_top = self.title_top + self.title_label.get_height() + self.subtitle_label.get_height() \
            + int(height * 0.07)
        step = int(height * 0.095)
        self.item_labels = {}
        self.item_rects = {}
        for index, (item, label, _) in enumerate(self.MAIN_ITEMS):
            self.item_labels[item] = {
                False: self._outlined(item_font, label.upper(), (235, 235, 240)),
                True: self._outlined(item_font, label.upper(), self.GOLD),
            }
            text = self.item_labels[item][False]
            # The whole row can be tapped, not just the letters
            self.item_rects[item] = pygame.Rect(self.main_left - 14, items_top + index * step - 6,
                                                max(text.get_width() + 60, int(width * 0.3)),
                                                text.get_height() + 12)
        self.description_top = items_top + len(self.MAIN_ITEMS) * step + int(height * 0.01)
        self.developer_label = self._outlined(small_font, DEVELOPER, (230, 230, 235))
        self.notice_fonts = (pygame.font.Font(None, max(30, int(height * 0.07))), self.description_font)

    def _draw_main(self, screen, resolution):
        screen.blit(self.main_image, (0, 0))
        screen.blit(self.title_label, (self.main_left, self.title_top))
        screen.blit(self.subtitle_label, (self.main_left - 2, self.title_top + self.title_label.get_height() - 4))
        for index, (item, _, description) in enumerate(self.MAIN_ITEMS):
            rect = self.item_rects[item]
            selected = index == self.selected_item
            if selected:
                # Highlight: a translucent plate and a gold bar on its left
                plate = pygame.Surface(rect.size, pygame.SRCALPHA)
                plate.fill((255, 205, 60, 38))
                screen.blit(plate, rect.topleft)
                pygame.draw.rect(screen, self.GOLD, (rect.x, rect.y, 5, rect.height))
            label = self.item_labels[item][selected]
            offset = 14 if selected else 0  # the highlighted entry steps forward
            screen.blit(label, (self.main_left + offset, rect.centery - label.get_height() // 2))
        description = self.MAIN_ITEMS[self.selected_item][2]
        text = self._outlined(self.description_font, description, (210, 210, 220), width=1)
        screen.blit(text, (self.main_left, self.description_top))
        self._draw_version(screen, resolution)
        margin = max(8, int(resolution[1] * 0.015))
        screen.blit(self.developer_label, self.developer_label.get_rect(
            bottomright=(resolution[0] - margin, resolution[1] - margin)))
        if self.notice_shown:
            self._draw_notice(screen, resolution)

    def _draw_notice(self, screen, resolution):
        """Story mode is not there yet."""
        title_font, text_font = self.notice_fonts
        title = title_font.render("Story Mode", True, self.GOLD)
        lines = [text_font.render(line, True, (235, 235, 240)) for line in
                 ("The game is still under development:", "this mode is not available yet.")]
        width = max(title.get_width(), *(line.get_width() for line in lines)) + 60
        height = title.get_height() + sum(line.get_height() + 6 for line in lines) + 50
        panel = pygame.Rect(0, 0, width, height)
        panel.center = (resolution[0] // 2, resolution[1] // 2)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(shade, (14, 16, 28, 235), shade.get_rect(), border_radius=14)
        screen.blit(shade, panel.topleft)
        pygame.draw.rect(screen, self.GOLD, panel, 2, border_radius=14)
        y = panel.top + 18
        screen.blit(title, title.get_rect(midtop=(panel.centerx, y)))
        y += title.get_height() + 10
        for line in lines:
            screen.blit(line, line.get_rect(midtop=(panel.centerx, y)))
            y += line.get_height() + 6

    @property
    def version_text(self):
        return f"v{__version__}"

    def _draw_version(self, screen, resolution):
        """The version, small, in the bottom-left corner of the main menu."""
        if self._version_label is None:
            font = pygame.font.Font(None, max(22, int(resolution[1] / 30)))
            text = font.render(self.version_text, True, (255, 255, 255))
            label = pygame.Surface((text.get_width() + 16, text.get_height() + 8), pygame.SRCALPHA)
            label.fill((15, 18, 30, 170))
            label.blit(text, (8, 4))
            self._version_label = label
        margin = max(8, int(resolution[1] * 0.015))
        screen.blit(self._version_label, (margin, resolution[1] - margin - self._version_label.get_height()))

    def open_online(self):
        """Online: the player's name, the character, the allies (for team
        matches), then the lobby."""
        self.online = True
        self.state = State.NAME_ENTRY
        pygame.key.start_text_input()  # shows the keyboard on a phone

    def confirm_name(self):
        self.player_name = self.player_name.strip()[:self.NAME_LENGTH] or roster.display_name(self.selected_character)
        settings = user_settings.load()
        if settings.get("player_name") != self.player_name:
            settings["player_name"] = self.player_name
            user_settings.save(settings)
        pygame.key.stop_text_input()
        self.state = State.CHARACTER_SELECT

    def _draw_name_entry(self, screen, resolution):
        screen.blit(self.menu_image, (0, 0))
        width, height = resolution
        title = self.character_title_font.render("Your name", True, (255, 230, 120))
        screen.blit(title, title.get_rect(center=(width / 2, height * 0.26)))
        under = self.difficulty_font.render("What the other players see online", True, (220, 220, 230))
        screen.blit(under, under.get_rect(center=(width / 2, height * 0.26 + title.get_height())))
        field = pygame.Rect(0, 0, min(width - 80, 520), self.character_font.get_linesize() + 24)
        field.center = (width / 2, height * 0.46)
        pygame.draw.rect(screen, (245, 245, 250), field, border_radius=10)
        pygame.draw.rect(screen, self.GOLD, field, 3, border_radius=10)
        caret = "|" if (pygame.time.get_ticks() // 500) % 2 == 0 else " "
        shown = self.player_name or ""
        text = self.character_font.render(shown + caret, True, (20, 20, 30))
        screen.blit(text, text.get_rect(midleft=(field.left + 16, field.centery)))
        if not shown:
            placeholder = self.character_font.render(roster.display_name(self.selected_character), True, (160, 160, 170))
            screen.blit(placeholder, placeholder.get_rect(midleft=(field.left + 16 + text.get_width(), field.centery)))
        self.name_field_rect = field
        label = self.button_font.render("OK", True, (255, 255, 255))
        self.name_ok_rect = label.get_rect(center=(width / 2, field.bottom + height * 0.1)).inflate(80, 18)
        pygame.draw.rect(screen, (40, 110, 60), self.name_ok_rect, border_radius=10)
        pygame.draw.rect(screen, (245, 245, 245), self.name_ok_rect, 2, border_radius=10)
        screen.blit(label, label.get_rect(center=self.name_ok_rect.center))
        hint = ("A: OK   B: back" if self.gamepad_hints
                else "Type your name, then Enter or OK  (Esc: back)")
        instructions = self.character_font.render(hint, True, (255, 255, 255))
        screen.blit(instructions, instructions.get_rect(center=(width / 2, height * 0.85)))
        self._draw_back_button(screen, resolution)

    def go_back(self):
        """One screen back (Esc or the Back button): opponents -> allies ->
        character -> main menu."""
        if self.state == State.ENEMY_SELECT:
            self.state = State.ALLY_SELECT
        elif self.state == State.ALLY_SELECT:
            self.state = State.CHARACTER_SELECT
        elif self.state == State.CHARACTER_SELECT and self.online:
            self.state = State.NAME_ENTRY
            pygame.key.start_text_input()
        else:
            if self.state == State.NAME_ENTRY:
                pygame.key.stop_text_input()
            self.state = State.START
            self.online = False

    def _draw_back_button(self, screen, resolution):
        """Top-left: the way back on a touch screen (there is no Esc key)."""
        text = self.button_font.render("< Back", True, (255, 255, 255))
        margin = max(10, int(resolution[1] * 0.025))
        rect = text.get_rect(topleft=(margin + 14, margin + 8)).inflate(28, 16)
        rect.topleft = (margin, margin)
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((15, 18, 30, 200))
        screen.blit(shade, rect.topleft)
        pygame.draw.rect(screen, (245, 245, 245), rect, 2, border_radius=10)
        screen.blit(text, text.get_rect(center=rect.center))
        self.back_rect = rect

    @property
    def selected_enemy(self):
        """The first enemy (the one an older single-enemy setup used)."""
        return self.selected_enemies[0] if self.selected_enemies else None

    def _card_at(self, position):
        for character_name, rect in self.character_rects.items():
            if rect.collidepoint(position):
                return character_name
        return None

    def _choose_character(self, character_name):
        """The player chose his character: then his allies (online: for
        team matches)."""
        self.selected_character = character_name
        # He cannot also be his own ally
        if character_name in self.selected_allies:
            self.selected_allies.remove(character_name)
        self.focus = self.character_names.index(character_name)
        self.state = State.ALLY_SELECT

    def _toggle(self, character_name, enemies):
        """Pick or unpick a card. Past the most a side can have, the first
        picked one makes room."""
        if enemies:
            chosen, limit = self.selected_enemies, MAX_ENEMIES
        else:
            if character_name == self.selected_character:
                return  # already in the fight, as the player
            chosen, limit = self.selected_allies, MAX_ALLIES
        if character_name in chosen:
            chosen.remove(character_name)
        else:
            chosen.append(character_name)
            if len(chosen) > limit:
                chosen.pop(0)

    def _continue(self, enemies):
        """Allies chosen (or none): the enemies (online: the lobby). Enemies
        chosen: fight."""
        if not enemies and self.online:
            self.isPlaying = True
        elif not enemies:
            self.focus = self.character_names.index(self.selected_enemy or self.character_names[0])
            self.state = State.ENEMY_SELECT
        elif self.selected_enemies:
            self.isPlaying = True

    def _cycle_character(self, direction):
        current_index = self.character_names.index(self.selected_character)
        self.selected_character = self.character_names[(current_index + direction) % len(self.character_names)]

    # The four stats on a card: label, Stats field, bar colour
    STAT_ROWS = (("POW", "power", (235, 95, 70)), ("HP", "hp", (80, 200, 100)),
                 ("DEF", "defense", (90, 160, 240)), ("SPD", "speed", (245, 205, 70)))
    # Stats go from about 0.9 to 1.3 (1.0: average): a bar shows this range
    STAT_RANGE = (0.7, 1.4)

    # ---- Character screens -----------------------------------------------------
    # The portraits of everyone on the left (a grid), the one in focus on the
    # right: walking, with its stats. picking: None (the player's character),
    # "allies" or "enemies" (several, with a button to go on)
    SCREEN_TITLES = {
        None: "Choose your character",
        "allies": "Choose your allies (optional)",
        "enemies": "Choose your opponents",
        "online allies": "Your allies for team matches (optional)",
    }
    PICKING = {State.CHARACTER_SELECT: None, State.ALLY_SELECT: "allies", State.ENEMY_SELECT: "enemies"}
    WALK_FRAME_MS = 160
    grid_columns = 1

    def _focused(self):
        return self.character_names[self.focus % len(self.character_names)]

    def _set_focus(self, index, picking):
        self.focus = index % len(self.character_names)
        if picking is None:
            self.selected_character = self._focused()

    def _select_event(self, event, resolution, picking):
        """One event on a character screen."""
        count, columns = len(self.character_names), max(1, self.grid_columns)
        if picking is None and self.character_names[self.focus % count] != self.selected_character \
                and self.selected_character in self.character_names:
            self.focus = self.character_names.index(self.selected_character)
        if event.type == pygame.KEYDOWN:
            moves = {pygame.K_LEFT: -1, pygame.K_a: -1, pygame.K_RIGHT: 1, pygame.K_d: 1,
                     pygame.K_UP: -columns, pygame.K_w: -columns, pygame.K_DOWN: columns, pygame.K_s: columns}
            if event.key in moves:
                self._set_focus(self.focus + moves[event.key], picking)
            elif event.key == pygame.K_SPACE:
                if picking is None:
                    self._choose_character(self._focused())
                else:
                    self._toggle(self._focused(), picking == "enemies")
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                if picking is None:
                    self._choose_character(self._focused())
                else:
                    if picking == "enemies" and not self.selected_enemies:
                        # Enter on a card with none picked: that one
                        self._toggle(self._focused(), True)
                    self._continue(picking == "enemies")
            elif event.key == pygame.K_ESCAPE:
                self.go_back()
            return
        if event.type == pygame.MOUSEMOTION and not getattr(event, "touch", False):
            name = self._card_at(event.pos)
            if name is not None:
                self._set_focus(self.character_names.index(name), picking)  # the mouse shows what it points at
            return
        if not self._is_tap(event, resolution):
            return
        position = self._event_position(event, resolution)
        if self.back_rect is not None and self.back_rect.collidepoint(position):
            self.go_back()
        elif self.continue_rect is not None and self.continue_rect.collidepoint(position):
            if picking is None:
                self._choose_character(self._focused())
            else:
                self._continue(picking == "enemies")
        else:
            name = self._card_at(position)
            if name is None:
                return
            index = self.character_names.index(name)
            if picking is None:
                # A first tap shows the character on the right, a second
                # one (or the button) chooses it
                if index == self.focus % count and self._focus_shown:
                    self._choose_character(name)
                else:
                    self._set_focus(index, picking)
                    self._focus_shown = True
            else:
                self._set_focus(index, picking)
                self._toggle(name, picking == "enemies")

    _focus_shown = False

    def _portrait(self, character_name, size):
        """The character's portrait, scaled (pixel art: no smoothing), or None."""
        key = ("portrait", character_name, size)
        if key not in self._fitted_previews:
            face = portrait(character_name)
            self._fitted_previews[key] = None if face is None else pygame.transform.scale(face, (size, size))
        return self._fitted_previews[key]

    def _fitted_preview(self, character_name, max_width, max_height):
        """The standing sprite, shrunk if needed to fit (a character without
        a portrait). Cached per size."""
        key = (character_name, max_width, max_height)
        fitted = self._fitted_previews.get(key)
        if fitted is None:
            preview = self.character_previews[character_name]
            ratio = min(1, max_width / preview.get_width(), max_height / preview.get_height())
            size = (max(1, int(preview.get_width() * ratio)), max(1, int(preview.get_height() * ratio)))
            fitted = self._fitted_previews[key] = (
                preview if ratio == 1 else pygame.transform.scale(preview, size)
            )
        return fitted

    def _walk_frames(self, character_name, max_width, max_height):
        """Its "Walk Down" frames, scaled up by a whole factor to fit (big
        characters stay bigger), cached."""
        key = ("walk", character_name, max_width, max_height)
        frames = self._fitted_previews.get(key)
        if frames is None:
            animator = Animator(character_name)
            raw = animator.frames("Walk Down") or [animator.image]
            width = max(frame.get_width() for frame in raw)
            height = max(frame.get_height() for frame in raw)
            factor = max(1, min(max_width // max(1, width), max_height // max(1, height)))
            frames = self._fitted_previews[key] = [
                pygame.transform.scale(frame, (frame.get_width() * factor, frame.get_height() * factor))
                for frame in raw]
        return frames

    def _technique_names(self, character_name):
        key = ("techniques", character_name)
        if key not in self._fitted_previews:
            names = []
            try:
                with open(PathManager.character_json_path(character_name, "specials")) as file:
                    names = [entry["name"] for entry in json.load(file).get("techniques", [])]
            except (OSError, ValueError, KeyError):
                pass
            self._fitted_previews[key] = names
        return self._fitted_previews[key]

    def _fonts_for(self, height):
        key = ("fonts", height)
        fonts = self._fitted_previews.get(key)
        if fonts is None:
            fonts = self._fitted_previews[key] = (
                pygame.font.Font(None, max(30, int(height * 0.075))),   # title, name
                pygame.font.Font(None, max(18, int(height * 0.042))),   # stats, techniques
                pygame.font.Font(None, max(20, int(height * 0.05))),    # hint, button
            )
        return fonts

    def _draw_character_select(self, screen, resolution, picking=None):
        screen.blit(self.menu_image, (0, 0))
        width, height = resolution
        names = self.character_names
        if picking is None and self.selected_character in names:
            self.focus = names.index(self.selected_character)
        big_font, small_font, hint_font = self._fonts_for(height)
        title_key = "online allies" if picking == "allies" and self.online else picking
        title = big_font.render(self.SCREEN_TITLES[title_key], True, (255, 230, 120))
        screen.blit(title, title.get_rect(center=(width / 2, height * 0.07)))
        self._draw_back_button(screen, resolution)

        margin = max(12, int(width * 0.02))
        top = max(height * 0.14, self.back_rect.bottom + 6)
        bottom = height * 0.88
        split = width * 0.58
        self._draw_grid(screen, pygame.Rect(margin, top, split - margin * 1.5, bottom - top), picking)
        panel = pygame.Rect(split, top, width - split - margin, bottom - top)
        self._draw_details(screen, panel, picking, big_font, small_font, hint_font)

        if picking is None:
            hint = ("A: choose   B: back" if self.gamepad_hints
                    else "Tap to see a character, tap again to choose   (arrows + Enter)")
        else:
            limit = MAX_ALLIES if picking == "allies" else MAX_ENEMIES
            hint = (f"X: pick (up to {limit})   A: go on   B: back" if self.gamepad_hints
                    else f"Tap or Space to pick (up to {limit}), Enter to go on, Esc: back")
        text = hint_font.render(hint, True, (255, 255, 255))
        screen.blit(text, text.get_rect(center=(width / 2, (bottom + height) / 2)))

    def _draw_grid(self, screen, area, picking):
        names = self.character_names
        count = len(names)
        # As many columns as give the biggest portraits
        best = (0, 1)
        for columns in range(1, count + 1):
            rows = -(-count // columns)
            size = min(area.width / columns, area.height / rows)
            if size > best[0]:
                best = (size, columns)
        pitch, columns = best
        self.grid_columns = columns
        size = int(pitch * 0.9)
        rows = -(-count // columns)
        left = area.left + (area.width - pitch * columns) / 2
        chosen = {None: [self.selected_character], "allies": self.selected_allies,
                  "enemies": self.selected_enemies}[picking]
        _, small_font, _ = self._fonts_for(screen.get_height())
        self.character_rects.clear()
        for index, name in enumerate(names):
            row, column = divmod(index, columns)
            rect = pygame.Rect(int(left + column * pitch), int(area.top + row * pitch), size, size)
            self.character_rects[name] = rect
            face = self._portrait(name, size)
            if face is not None:
                screen.blit(face, rect)
            else:
                pygame.draw.rect(screen, (20, 20, 30), rect, border_radius=8)
                preview = self._fitted_preview(name, size - 8, size - 8)
                screen.blit(preview, preview.get_rect(center=rect.center))
            picked = name in chosen
            focused = index == self.focus % count
            if picked:
                colour = (120, 195, 255) if picking == "allies" else (255, 220, 100)
                pygame.draw.rect(screen, colour, rect.inflate(6, 6), 4, border_radius=8)
                if picking is not None:
                    badge = small_font.render(str(chosen.index(name) + 1), True, (20, 20, 30))
                    spot = pygame.Rect(0, 0, badge.get_width() + 10, badge.get_height() + 4)
                    spot.topright = (rect.right + 3, rect.top - 3)
                    pygame.draw.rect(screen, colour, spot, border_radius=6)
                    screen.blit(badge, badge.get_rect(center=spot.center))
            if focused:
                pygame.draw.rect(screen, (255, 255, 255), rect.inflate(12, 12), 3, border_radius=10)
            if picking == "allies" and name == self.selected_character:
                # The player cannot also be his own ally
                shade = pygame.Surface(rect.size, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 160))
                screen.blit(shade, rect)
                you = small_font.render("You", True, (255, 230, 120))
                screen.blit(you, you.get_rect(center=rect.center))

    def _draw_details(self, screen, panel, picking, big_font, small_font, hint_font):
        """The character in focus: name, walking, stats, techniques; and
        the button that goes on."""
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((10, 12, 22, 200))
        screen.blit(shade, panel.topleft)
        pygame.draw.rect(screen, (235, 235, 235), panel, 2, border_radius=10)
        name = self._focused()
        inner = panel.inflate(-24, -20)
        y = inner.top
        label = big_font.render(roster.display_name(name), True, (255, 255, 255))
        screen.blit(label, label.get_rect(midtop=(inner.centerx, y)))
        y += label.get_height() + 2
        if picking == "enemies":
            difficulty = self.enemy_difficulties.get(name) or enemy_profile(name).difficulty
            text = small_font.render(difficulty.label, True, difficulty.color)
            screen.blit(text, text.get_rect(midtop=(inner.centerx, y)))
            y += text.get_height() + 2

        button_height = hint_font.get_linesize() + 14
        line = small_font.get_linesize()
        techniques = self._technique_names(name)
        stats_height = line * len(self.STAT_ROWS)
        techniques_height = line * (1 + len(techniques)) if techniques else 0
        walk_height = inner.bottom - y - stats_height - techniques_height - button_height - 24
        frames = self._walk_frames(name, inner.width, max(32, walk_height))
        frame = frames[(pygame.time.get_ticks() // self.WALK_FRAME_MS) % len(frames)]
        screen.blit(frame, frame.get_rect(midbottom=(inner.centerx, y + max(32, walk_height))))
        y += max(32, walk_height) + 6

        stats = character_stats(name)
        low, high = self.STAT_RANGE
        label_width = small_font.size("POW ")[0]
        value_width = small_font.size("130")[0] + 6
        bar_height = max(5, line // 2)
        for stat_label, field, colour in self.STAT_ROWS:
            value = getattr(stats, field)
            screen.blit(small_font.render(stat_label, True, (215, 215, 225)), (inner.left, y))
            bar = pygame.Rect(inner.left + label_width, y + (line - bar_height) // 2 - 1,
                              max(10, inner.width - label_width - value_width), bar_height)
            pygame.draw.rect(screen, (30, 30, 40), bar, border_radius=3)
            share = max(0.05, min(1.0, (value - low) / (high - low)))
            pygame.draw.rect(screen, colour, (bar.x, bar.y, round(bar.width * share), bar.height), border_radius=3)
            number = small_font.render(str(round(value * 100)), True, (255, 255, 255))
            screen.blit(number, number.get_rect(topright=(inner.right, y)))
            y += line
        if techniques:
            y += 4
            for technique in techniques:
                text = small_font.render(f"- {technique}", True, (200, 215, 255))
                screen.blit(text, (inner.left, y))
                y += line

        # The button that goes on
        if picking is None:
            label, active = f"Choose {roster.display_name(name)}", True
        elif picking == "allies":
            label = "To the lobby" if self.online else ("Next" if self.selected_allies else "Fight alone")
            active = True
        else:
            active = bool(self.selected_enemies)
            label = "Fight!" if active else "Pick at least one"
        text = hint_font.render(label, True, (255, 255, 255) if active else (170, 170, 170))
        self.continue_rect = pygame.Rect(0, 0, min(inner.width, text.get_width() + 40), button_height)
        self.continue_rect.midbottom = (inner.centerx, panel.bottom - 10)
        pygame.draw.rect(screen, (40, 110, 60) if active else (60, 60, 70), self.continue_rect, border_radius=10)
        pygame.draw.rect(screen, (245, 245, 245), self.continue_rect, 2, border_radius=10)
        screen.blit(text, text.get_rect(center=self.continue_rect.center))

    def controls_guide(self):
        """The control guide's lines, with the keys and buttons in use
        (see controls.py: the player may have changed them)."""
        controls = self.controls

        def keys(*actions):
            return " / ".join(name for action in actions for name in controls.key_names(action))

        def buttons(*actions):
            return "/".join(button.upper() for action in actions for button in controls.pad_buttons.get(action, ()))

        pad_line = ", ".join(f"{buttons(*actions)} {label}" for actions, label in (
            (("run",), "run"), (("attack",), "attack"), (("guard",), "guard"), (("special",), "special"),
            (("super",), "transform"), (("tech_prev", "tech_next"), "technique"),
            (("form_prev", "form_next"), "level")) if buttons(*actions))
        return [
            "Move: Arrow keys or the on-screen stick",
            f"Run: hold {keys('run')} or push the stick to the edge",
            f"Attack: {keys('attack')} or the AUTO button (one punch or kick per press)",
            f"Guard: hold {keys('guard')} or the DEFENSE button",
            f"Special technique: {keys('special')} or the blast button",
            f"Choose technique: {keys('tech_prev', 'tech_next')} or the arrows above it",
            f"Super Saiyan: {keys('super')} or the transform button",
            f"Super Saiyan level (Goku): {keys('form_prev', 'form_next')} or the arrows above it",
            f"Talk: {keys('talk')}",
            "Quit or main menu: Esc key or the X button (top right)",
            "Online 1v1: O key or Online Mode in the main menu",
            "Controller (ROG Ally, Xbox...): stick move, Menu pause,",
            pad_line,
        ]

    def _draw_options(self, screen, resolution):
        screen.blit(self.menu_image, (0, 0))
        lines = ["Controls", *self.controls_guide(), "Press Esc or tap to return"]
        line_height = int(self.options_font_size * 1.25)
        title_height = int(line_height * 1.3)
        block_height = title_height + line_height * (len(lines) - 1)
        y = (resolution[1] - block_height) / 2 + line_height / 2
        # Dark panel behind the text so it reads over the artwork
        widest = max(self.options_font.size(line)[0] for line in lines)
        panel = pygame.Rect(0, 0, widest + line_height * 2, block_height + line_height)
        panel.center = (resolution[0] / 2, resolution[1] / 2)
        shade = pygame.Surface(panel.size, pygame.SRCALPHA)
        shade.fill((10, 12, 20, 190))
        screen.blit(shade, panel.topleft)
        for index, line in enumerate(lines):
            font = self.options_title_font if index == 0 else self.options_font
            color = (255, 230, 120) if index == 0 else (255, 255, 255)
            text = font.render(line, True, color)
            screen.blit(text, text.get_rect(center=(resolution[0] / 2, y)))
            y += title_height if index == 0 else line_height

    @staticmethod
    def _is_tap(event, resolution):
        # A touch counts once, not again as its mouse copy (see taps.py)
        return tap_position(event, resolution) is not None

    @staticmethod
    def _event_position(event, resolution):
        if event.type == pygame.FINGERDOWN:
            return event.x * resolution[0], event.y * resolution[1]
        return event.pos