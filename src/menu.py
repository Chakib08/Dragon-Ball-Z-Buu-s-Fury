import pygame
from typing import List
from enum import Enum

from pathmanager import PathManager
from animation import Animation
from difficulty import enemy_profile
from map import MAX_ALLIES, MAX_ENEMIES

# Define a custom event for the arrow blitting
ARROW_BLIT_EVENT = pygame.USEREVENT + 1

class State(Enum):
    START = 1
    OPTIONS = 2
    CHARACTER_SELECT = 3
    ENEMY_SELECT = 4
    ALLY_SELECT = 5

# TODO: Remove magic numbers, retreive the latters from the app config
class Menu:
    # Start/Options sit at this fraction of the screen width (the background
    # image is stretched to the screen), with the arrow just left of them
    BUTTONS_X = 680 / 1200
    ARROW_GAP = 25

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
        # The control guide must fit on any screen height
        self.options_font_size = max(20, min(42, int(resolution[1] / 25)))
        self.options_font = pygame.font.Font(None, self.options_font_size)
        self.options_title_font = pygame.font.Font(None, int(self.options_font_size * 1.4))

        # Arrow selector image
        self.arrow_image = pygame.image.load(PathManager.menu_image_path("arrow.png"))
        self.arrow_image = pygame.transform.scale(self.arrow_image, (50, 50))
        
        self.isPlaying = False
        # True when the character was chosen for an online match
        self.online = False
        self.online_font = pygame.font.Font(None, max(30, int(resolution[1] / 22)))
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
        self.button_font = pygame.font.Font(None, 40)
        self.enemy_difficulties = {name: enemy_profile(name).difficulty for name in self.character_names}
        self.difficulty_font = pygame.font.Font(None, 32)
        self.character_font = pygame.font.Font(None, 42)
        self.character_title_font = pygame.font.Font(None, 58)
        self.character_previews = {}
        self._fitted_previews = {}
        self.character_rects = {}
        for character_name in self.character_names:
            preview = Animation(character_name).image
            self.character_previews[character_name] = pygame.transform.scale(
                preview, (preview.get_width() * 4, preview.get_height() * 4)
            )
        
        # Set the timer to trigger the event every specific laps of time
        pygame.time.set_timer(ARROW_BLIT_EVENT, 500)
        
        # Arrow visibility flag and timestamp
        self.arrow_visible = False
        self.arrow_last_time = pygame.time.get_ticks()
        
    def launch_menu(self, screen: pygame.Surface, resolution: tuple, events: List[pygame.event.Event]) -> None:
        # Set up the start image rect
        image_start_rect = self.start_image.get_rect()
        image_start_rect.center = (resolution[0] * self.BUTTONS_X, resolution[1] / 1.5)
        # Set up the options image rect
        image_options_rect = self.options_image.get_rect()
        image_options_rect.center = (resolution[0] * self.BUTTONS_X, resolution[1] / 1.35)
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
                        self.state = State.START
                        self.online = False
                elif self._is_tap(event, resolution):
                    chosen = self._card_at(self._event_position(event, resolution))
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
                        self.state = State.ALLY_SELECT if choosing_enemies else State.CHARACTER_SELECT
                elif self._is_tap(event, resolution):
                    position = self._event_position(event, resolution)
                    if self.continue_rect is not None and self.continue_rect.collidepoint(position):
                        self._continue(choosing_enemies)
                    else:
                        name = self._card_at(position)
                        if name is not None:
                            self.focus = self.character_names.index(name)
                            self._toggle(name, choosing_enemies)
                if self.isPlaying or self.state not in (State.ALLY_SELECT, State.ENEMY_SELECT):
                    break
            return

        self.start_image = self.menu_images[State.START][self.state == State.START]
        self.options_image = self.menu_images[State.OPTIONS][self.state == State.OPTIONS]

        # Blit images
        screen.blit(self.menu_image, (0, 0))
        screen.blit(self.start_image, image_start_rect.topleft)
        screen.blit(self.options_image, image_options_rect.topleft)
        online_rect = self._draw_online_button(screen, resolution, image_options_rect)
        
        # Manage arrow visibility
        current_time = pygame.time.get_ticks()
        if self.arrow_visible and current_time - self.arrow_last_time >= 200:
            self.arrow_visible = False
        
        # Blit the arrow image according to the selected state
        if self.arrow_visible:
            if self.state == State.START:
                image_arrow_rect.center = (image_start_rect.left - self.ARROW_GAP, resolution[1] / 1.5)
            elif self.state == State.OPTIONS:
                image_arrow_rect.center = (image_options_rect.left - self.ARROW_GAP, resolution[1] / 1.35)
            screen.blit(self.arrow_image, image_arrow_rect.topleft)
        # Handle keyboard and touch selection.
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_UP, pygame.K_w):
                    self.state = State.START
                if event.key == pygame.K_RETURN and self.state == State.START:
                    self.state = State.CHARACTER_SELECT
                elif event.key in (pygame.K_DOWN, pygame.K_s):
                    self.state = State.OPTIONS                                                 
            elif event.type == ARROW_BLIT_EVENT:
                self.arrow_visible = True
                self.arrow_last_time = current_time
            elif self._is_tap(event, resolution):
                position = self._event_position(event, resolution)
                if image_start_rect.collidepoint(position):
                    self.state = State.CHARACTER_SELECT
                elif image_options_rect.collidepoint(position):
                    self.state = State.OPTIONS
                elif online_rect.collidepoint(position):
                    self.open_online()
            if event.type == pygame.KEYDOWN and event.key == pygame.K_o:
                self.open_online()

    def open_online(self):
        """Pick a character, then go to the online lobby."""
        self.online = True
        self.state = State.CHARACTER_SELECT

    def _draw_online_button(self, screen, resolution, options_rect):
        """Text button under OPTIONS (the others are images)."""
        text = self.online_font.render("ONLINE 1V1", True, (255, 220, 90))
        rect = text.get_rect(midtop=(options_rect.centerx, options_rect.bottom + options_rect.height * 0.5))
        box = rect.inflate(24, 12)
        shade = pygame.Surface(box.size, pygame.SRCALPHA)
        shade.fill((15, 18, 30, 200))
        screen.blit(shade, box.topleft)
        pygame.draw.rect(screen, (255, 220, 90), box, 2, border_radius=6)
        screen.blit(text, rect)
        return box

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
            hint = "Tap a character, or use Left/Right and Enter"
            self.continue_rect = None
        else:
            limit = MAX_ALLIES if picking == "allies" else MAX_ENEMIES
            hint = f"Tap or Space to pick (up to {limit}), Enter to go on, Esc: back"
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
            "Online 1v1: O key or the ONLINE button",
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
        return (
            event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        ) or event.type == pygame.FINGERDOWN

    @staticmethod
    def _event_position(event, resolution):
        if event.type == pygame.FINGERDOWN:
            return event.x * resolution[0], event.y * resolution[1]
        return event.pos