import pygame
from typing import List
from enum import Enum

from pathmanager import PathManager
from animation import Animator
from difficulty import enemy_profile
from taps import tap_position
from version import __version__
from map import MAX_ALLIES, MAX_ENEMIES

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
    NOTICE_MS = 2600
    # Show the controller's buttons in the hints (set by the game)
    gamepad_hints = False

    def __init__(self, resolution) -> None:
        artwork = pygame.image.load(PathManager.menu_image_path(BACKGROUND_IMAGE))
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
        # Highlighted entry (Arcade: the one most players want)
        self.selected_item = 1
        # "Not available yet" message (Story mode) until this time
        self.notice_until = 0

        # The control guide must fit on any screen height
        self.options_font_size = max(20, min(42, int(resolution[1] / 25)))
        self.options_font = pygame.font.Font(None, self.options_font_size)
        self.options_title_font = pygame.font.Font(None, int(self.options_font_size * 1.4))

        self.isPlaying = False
        # True when the character was chosen for an online match
        self.online = False
        self.state = State.START
        self.character_names = ("goku", "vegeta", "gohan", "trunks", "broly")
        self.selected_character = "goku"
        # The team of the story mode, chosen after the character: his allies
        # (none to fight alone) and the enemies (at least one)
        self.selected_allies = []
        self.selected_enemies = ["gohan"]
        # Card the keyboard is on, in the ally and enemy screens
        self.focus = 0
        self.continue_rect = None
        self.back_rect = None
        self.button_font = pygame.font.Font(None, 40)
        self._version_label = None
        self.enemy_difficulties = {name: enemy_profile(name).difficulty for name in self.character_names}
        self.difficulty_font = pygame.font.Font(None, 32)
        self.character_font = pygame.font.Font(None, 42)
        self.character_title_font = pygame.font.Font(None, 58)
        self.character_previews = {}
        self._fitted_previews = {}
        self.character_rects = {}
        for character_name in self.character_names:
            preview = Animator(character_name).image
            self.character_previews[character_name] = pygame.transform.scale(
                preview, (preview.get_width() * 4, preview.get_height() * 4)
            )
        

    def launch_menu(self, screen: pygame.Surface, resolution: tuple, events: List[pygame.event.Event]) -> None:
        if self.state == State.OPTIONS:
            self._draw_options(screen, resolution)
            for event in events:
                if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN):
                    self.state = State.START
                elif self._is_tap(event, resolution):
                    self.state = State.START
            return

        if self.state == State.CHARACTER_SELECT:
            self._draw_character_select(screen, resolution)
            for event in events:
                chosen = None
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self._cycle_character(-1)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self._cycle_character(1)
                    elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        chosen = self.selected_character
                    elif event.key == pygame.K_ESCAPE:
                        self.go_back()
                elif self._is_tap(event, resolution):
                    position = self._event_position(event, resolution)
                    if self.back_rect is not None and self.back_rect.collidepoint(position):
                        self.go_back()
                        break
                    chosen = self._card_at(position)
                if chosen is not None:
                    self._choose_character(chosen)
                    break
            return

        if self.state in (State.ALLY_SELECT, State.ENEMY_SELECT):
            choosing_enemies = self.state == State.ENEMY_SELECT
            self._draw_character_select(screen, resolution, "enemies" if choosing_enemies else "allies")
            for event in events:
                if event.type == pygame.KEYDOWN:
                    if event.key in (pygame.K_LEFT, pygame.K_a):
                        self.focus = (self.focus - 1) % len(self.character_names)
                    elif event.key in (pygame.K_RIGHT, pygame.K_d):
                        self.focus = (self.focus + 1) % len(self.character_names)
                    elif event.key == pygame.K_SPACE:
                        self._toggle(self.character_names[self.focus], choosing_enemies)
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        if choosing_enemies and not self.selected_enemies:
                            # Enter on a card with none picked: that one
                            self._toggle(self.character_names[self.focus], True)
                        self._continue(choosing_enemies)
                    elif event.key == pygame.K_ESCAPE:
                        self.go_back()
                elif self._is_tap(event, resolution):
                    position = self._event_position(event, resolution)
                    if self.back_rect is not None and self.back_rect.collidepoint(position):
                        self.go_back()
                    elif self.continue_rect is not None and self.continue_rect.collidepoint(position):
                        self._continue(choosing_enemies)
                    else:
                        name = self._card_at(position)
                        if name is not None:
                            self.focus = self.character_names.index(name)
                            self._toggle(name, choosing_enemies)
                # The screen changed (Back, Next, Fight!): the rest is not for it
                if self.isPlaying or self.state != (State.ENEMY_SELECT if choosing_enemies else State.ALLY_SELECT):
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
        """Pick a character, then go to the online lobby."""
        self.online = True
        self.state = State.CHARACTER_SELECT

    def go_back(self):
        """One screen back (Esc or the Back button): opponents -> allies ->
        character -> main menu."""
        if self.state == State.ENEMY_SELECT:
            self.state = State.ALLY_SELECT
        elif self.state == State.ALLY_SELECT:
            self.state = State.CHARACTER_SELECT
        else:
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
        """The player chose his character: then his allies, except online
        where the opponent is another player."""
        self.selected_character = character_name
        # He cannot also be his own ally
        if character_name in self.selected_allies:
            self.selected_allies.remove(character_name)
        if self.online:
            self.isPlaying = True
        else:
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
        """Allies chosen (or none): the enemies. Enemies chosen: fight."""
        if not enemies:
            self.focus = self.character_names.index(self.selected_enemy or self.character_names[0])
            self.state = State.ENEMY_SELECT
        elif self.selected_enemies:
            self.isPlaying = True

    def _cycle_character(self, direction):
        current_index = self.character_names.index(self.selected_character)
        self.selected_character = self.character_names[(current_index + direction) % len(self.character_names)]

    def _fitted_preview(self, character_name, max_width, max_height):
        """The preview, shrunk if needed to fit in its card (Broly's sprite
        is twice the size of the others). Cached per size."""
        key = (character_name, max_width, max_height)
        fitted = self._fitted_previews.get(key)
        if fitted is None:
            preview = self.character_previews[character_name]
            ratio = min(1, max_width / preview.get_width(), max_height / preview.get_height())
            size = (int(preview.get_width() * ratio), int(preview.get_height() * ratio))
            fitted = self._fitted_previews[key] = (
                preview if ratio == 1 else pygame.transform.scale(preview, size)
            )
        return fitted

    SCREEN_TITLES = {
        None: "Choose your character",
        "allies": "Choose your allies (optional)",
        "enemies": "Choose your opponents",
    }

    def _draw_character_select(self, screen, resolution, picking=None):
        """The character cards. picking: None to choose the player's
        character, "allies" or "enemies" to pick several (with a button to
        go on)."""
        screen.blit(self.menu_image, (0, 0))
        title = self.character_title_font.render(self.SCREEN_TITLES[picking], True, (255, 230, 120))
        screen.blit(title, title.get_rect(center=(resolution[0] / 2, resolution[1] * 0.22)))

        card_width = min(220, resolution[0] // (len(self.character_names) + 1))
        # Cards fill 30-76% of the height, the hint sits below them
        card_height = min(300, int(resolution[1] * 0.40))
        spacing = (resolution[0] - card_width * len(self.character_names)) / (len(self.character_names) + 1)
        top = resolution[1] * 0.36
        self.character_rects.clear()
        chosen = {None: [self.selected_character], "allies": self.selected_allies,
                  "enemies": self.selected_enemies}[picking]

        for index, character_name in enumerate(self.character_names):
            rect = pygame.Rect(
                spacing * (index + 1) + card_width * index,
                top,
                card_width,
                card_height,
            )
            self.character_rects[character_name] = rect
            selected = character_name in chosen
            # The player's own character cannot be his ally
            unavailable = picking == "allies" and character_name == self.selected_character
            focused = picking is not None and index == self.focus
            colour = (25, 45, 80) if selected and picking == "allies" else (80, 60, 25) if selected else (20, 20, 30)
            pygame.draw.rect(screen, colour, rect, border_radius=12)
            border = (120, 195, 255) if selected and picking == "allies" else (255, 220, 100) if selected \
                else (255, 255, 255) if focused else (180, 180, 190)
            pygame.draw.rect(screen, border, rect, width=4 if selected or focused else 2, border_radius=12)

            preview = self._fitted_preview(character_name, card_width - 16, int(card_height * 0.62))
            if picking == "enemies":
                # The opponents face the player's character
                preview = pygame.transform.flip(preview, True, False)
            preview_y = rect.top + card_height * (0.42 if picking == "enemies" else 0.48)
            screen.blit(preview, preview.get_rect(center=(rect.centerx, preview_y)))
            label = self.character_font.render(character_name.title(), True, (255, 255, 255))
            label_y = rect.bottom - (58 if picking == "enemies" else 42)
            screen.blit(label, label.get_rect(center=(rect.centerx, label_y)))
            if picking == "enemies":
                difficulty = self.enemy_difficulties[character_name]
                text = self.difficulty_font.render(difficulty.label, True, difficulty.color)
                screen.blit(text, text.get_rect(center=(rect.centerx, rect.bottom - 26)))
            if selected and picking is not None:
                # Order of the pick, in the corner
                number = self.difficulty_font.render(str(chosen.index(character_name) + 1), True, border)
                screen.blit(number, number.get_rect(topright=(rect.right - 10, rect.top + 8)))
            if unavailable:
                shade = pygame.Surface(rect.size, pygame.SRCALPHA)
                shade.fill((0, 0, 0, 150))
                screen.blit(shade, rect.topleft)
                you = self.difficulty_font.render("You", True, (255, 230, 120))
                screen.blit(you, you.get_rect(center=rect.center))

        if picking is None:
            hint = ("A: choose   B: back" if self.gamepad_hints
                    else "Tap a character, or use Left/Right and Enter")
            self.continue_rect = None
        else:
            limit = MAX_ALLIES if picking == "allies" else MAX_ENEMIES
            hint = (f"X: pick (up to {limit})   A: go on   B: back" if self.gamepad_hints
                    else f"Tap or Space to pick (up to {limit}), Enter to go on, Esc: back")
            if picking == "allies":
                label = "Next" if chosen else "Fight alone"
            else:
                label = "Fight!" if chosen else "Pick at least one"
            text = self.button_font.render(label, True, (255, 255, 255) if picking == "allies" or chosen
                                           else (170, 170, 170))
            self.continue_rect = text.get_rect(center=(resolution[0] / 2, top + card_height + resolution[1] * 0.08))
            self.continue_rect.inflate_ip(40, 18)
            pygame.draw.rect(screen, (40, 110, 60) if picking == "allies" or chosen else (60, 60, 70),
                             self.continue_rect, border_radius=10)
            pygame.draw.rect(screen, (245, 245, 245), self.continue_rect, 2, border_radius=10)
            screen.blit(text, text.get_rect(center=self.continue_rect.center))
        self._draw_back_button(screen, resolution)
        instructions = self.character_font.render(hint, True, (255, 255, 255))
        hint_y = resolution[1] * (0.85 if picking is None else 0.93)
        screen.blit(instructions, instructions.get_rect(center=(resolution[0] / 2, hint_y)))

    def _draw_options(self, screen, resolution):
        screen.blit(self.menu_image, (0, 0))
        lines = [
            "Controls",
            "Move: Arrow keys or the on-screen stick",
            "Run: Hold Space or push the stick to the edge",
            "Attack: A key or the AUTO button (one punch or kick per press)",
            "Guard: hold F or the DEFENSE button",
            "Special technique: D key or the blast button",
            "Choose technique: Q / E or the arrows above it",
            "Super Saiyan: S key or the transform button",
            "Super Saiyan level (Goku): Z / X or the arrows above it",
            "Talk: T key",
            "Quit or main menu: Esc key or the X button (top right)",
            "Online 1v1: O key or Online Mode in the main menu",
            "Controller (ROG Ally, Xbox...): stick move, LT run, A attack, B guard,",
            "X special, Y transform, LB/RB technique, RT level, Menu pause",
            "Press Esc or tap to return",
        ]
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