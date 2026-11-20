"""What the fight shows on screen besides the fighters: the player's HP and
KI bars with the selected technique (top left), one row per ally under them
and per enemy on the right (the team panels), a thin bar over each NPC and
the charge bar of a technique being charged.

It only reads the fight (CombatSystem): nothing here changes it.
"""

import pygame


class CombatHud:
    # ---- Team panels (top corners) ------------------------------------------------
    # One compact row per fighter: the allies under the player's bars (left),
    # the enemies (or the online opponent) on the right, under the quit button.
    # The bottom corners stay free for the thumbs (stick and buttons).
    PANEL_ROW_WIDTH = 180
    PANEL_NAME_WIDTH = 66
    PANEL_BAR_HEIGHT = 9
    PANEL_ROW_GAP = 4
    PANEL_MARGIN = 20
    PANEL_PADDING = 4
    ALLY_PANEL_TOP = 112

    # ---- Bars over the fighters ---------------------------------------------------
    # Thin and without names (the panels have them): who is who in a crowd,
    # and how hurt
    OVERHEAD_BAR_HEIGHT = 5
    OVERHEAD_BAR_GAP = 4
    OVERHEAD_BAR_MIN_WIDTH = 28
    OVERHEAD_BAR_MAX_WIDTH = 60

    ENEMY_COLOR = (225, 70, 60)
    ALLY_COLOR = (120, 195, 255)
    SUPER_COLOR = (245, 205, 60)
    KO_COLOR = (125, 125, 135)
    HP_COLOR = (70, 200, 90)
    KI_COLOR = (65, 145, 245)
    FRAME_COLOR = (235, 235, 235)
    BAR_BACKGROUND = (35, 35, 42)

    def __init__(self, combat):
        self.combat = combat
        self.font = pygame.font.Font(None, 30)
        self.name_font = pygame.font.Font(None, 22)
        # Text (and panel plates) are rendered once and reused every frame
        self._labels = {}

    @property
    def screen_size(self):
        return self.combat.screen_size

    def _label(self, text, font, color=(255, 255, 255)):
        key = (text, font, color)
        label = self._labels.get(key)
        if label is None:
            label = self._labels[key] = font.render(text, True, color)
        return label

    def _plate(self, width, height):
        key = ("plate", width, height)
        plate = self._labels.get(key)
        if plate is None:
            plate = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.draw.rect(plate, (12, 14, 24, 165), plate.get_rect(), border_radius=6)
            self._labels[key] = plate
        return plate

    # ---- The player's bars --------------------------------------------------------
    def draw(self, screen):
        player = self.combat.player
        self._draw_bar(screen, "HP", player.hp, player.max_hp, self.HP_COLOR, 20)
        ki_color = self.SUPER_COLOR if player.powered_up else self.KI_COLOR
        self._draw_bar(screen, "KI", player.ki, player.max_ki, ki_color, 58)
        technique = self.combat.technique
        if technique is not None:
            # Selected technique and its cost, dimmed while there is not enough ki
            color = (255, 230, 120) if player.ki >= technique.cost else (150, 150, 160)
            label = self._label(f"{technique.name} ({technique.cost} KI)", self.name_font, color)
            screen.blit(label, (62, 88))
        self.draw_team_panels(screen)

    def _draw_bar(self, screen, label, value, maximum, color, y):
        x = 20
        bar_width = min(260, self.screen_size[0] // 3)
        bar_height = 22
        screen.blit(self._label(label, self.font), (x, y))
        bar_x = x + 42
        bar_y = y + 3
        pygame.draw.rect(screen, self.BAR_BACKGROUND, (bar_x, bar_y, bar_width, bar_height))
        fraction = max(0, min(1, value / maximum)) if maximum else 0
        pygame.draw.rect(screen, color, (bar_x, bar_y, round(bar_width * fraction), bar_height))
        pygame.draw.rect(screen, self.FRAME_COLOR, (bar_x, bar_y, bar_width, bar_height), 2)

    def draw_charge(self, screen, to_screen_rect):
        """A small bar above the player while a technique charges."""
        if not self.combat.charging:
            return
        on_screen = pygame.Rect(to_screen_rect(self.combat.player.rect))
        width = max(48, on_screen.width)
        bar = pygame.Rect(0, 0, width, 8)
        bar.midbottom = (on_screen.centerx, on_screen.top - 6)
        level = self.combat.charge_level
        pygame.draw.rect(screen, self.BAR_BACKGROUND, bar)
        color = (255, 230, 120) if level >= 1 else (120, 210, 255)
        pygame.draw.rect(screen, color, (bar.x, bar.y, round(bar.width * level), bar.height))
        pygame.draw.rect(screen, self.FRAME_COLOR, bar, 1)

    # ---- Team panels --------------------------------------------------------------
    def _right_panel_top(self):
        """Just under the quit button (see quit_prompt.QuitPrompt)."""
        radius = max(22, int(min(self.screen_size) * 0.034))
        return radius // 2 + radius * 2 + 12

    def draw_team_panels(self, screen):
        """The allies' rows (left) and the enemies' (right); returns the
        rectangles of the rows drawn, allies first."""
        rows = []
        y = self.ALLY_PANEL_TOP
        for ally in self.combat.allies:
            rows.append(self._draw_panel_row(screen, ally, 62, y, ally=True))
            y = rows[-1].bottom + self.PANEL_ROW_GAP + 2 * self.PANEL_PADDING
        x = self.screen_size[0] - self.PANEL_MARGIN - self.PANEL_ROW_WIDTH
        y = self._right_panel_top()
        for enemy in self.combat.enemies:
            rows.append(self._draw_panel_row(screen, enemy, x, y, ally=False))
            y = rows[-1].bottom + self.PANEL_ROW_GAP + 2 * self.PANEL_PADDING
        return rows

    def _draw_panel_row(self, screen, fighter, x, y, ally):
        """One line: the name, then a small HP bar (gold frame while Super
        Saiyan; greyed out with "KO" once knocked out)."""
        knocked_out = fighter.hp <= 0
        height = max(self.name_font.get_height(), self.PANEL_BAR_HEIGHT)
        # A dark plate behind the row, so it reads over grass, water or sky
        plate = self._plate(self.PANEL_ROW_WIDTH + 2 * self.PANEL_PADDING, height + 2 * self.PANEL_PADDING)
        screen.blit(plate, (x - self.PANEL_PADDING, y - self.PANEL_PADDING))
        name = getattr(fighter, "bar_label", None) or fighter.character_name.capitalize()
        if knocked_out:
            color = self.KO_COLOR
            name += " KO"
        elif ally:
            color = self.ALLY_COLOR
        else:
            # An enemy's name in the colour of its difficulty (Hard: red)
            difficulty = getattr(fighter, "difficulty", None)
            color = tuple(difficulty.color) if difficulty is not None else (255, 255, 255)
        label = self._label(name, self.name_font, color)
        screen.blit(label, (x, y + (height - label.get_height()) // 2))
        bar_left = x + max(self.PANEL_NAME_WIDTH, label.get_width() + 6)
        bar = pygame.Rect(bar_left, y + (height - self.PANEL_BAR_HEIGHT) // 2,
                          max(20, x + self.PANEL_ROW_WIDTH - bar_left), self.PANEL_BAR_HEIGHT)
        pygame.draw.rect(screen, self.BAR_BACKGROUND, bar)
        fraction = max(0, min(1, fighter.hp / fighter.max_hp)) if fighter.max_hp else 0
        if fraction > 0:
            pygame.draw.rect(screen, self.HP_COLOR, (bar.x, bar.y, round(bar.width * fraction), bar.height))
        frame = self.SUPER_COLOR if fighter.powered_up and not knocked_out else self.FRAME_COLOR
        pygame.draw.rect(screen, frame, bar, 1)
        return pygame.Rect(x, y, self.PANEL_ROW_WIDTH, height)

    # ---- Bars over the fighters -----------------------------------------------------
    def draw_npc_bars(self, screen, npcs, to_screen_rect):
        """A thin bar over each NPC (and online opponent): blue for allies,
        red for enemies, gold-framed while Super Saiyan. Returns the bars.

        to_screen_rect converts a rect in map coordinates to screen coordinates.
        The bar stays (empty) during the knock-out animation, then disappears.
        """
        placed = []
        shown = [(npc, pygame.Rect(to_screen_rect(npc.rect))) for npc in npcs if not npc.faint_finished]
        # The lowest on screen first: theirs stay right above them, and with
        # several fighters close together the others move aside or up
        # instead of covering each other
        shown.sort(key=lambda item: item[1].top, reverse=True)
        for npc, on_screen in shown:
            width = max(self.OVERHEAD_BAR_MIN_WIDTH, min(self.OVERHEAD_BAR_MAX_WIDTH, int(on_screen.width * 0.6)))
            start = pygame.Rect(0, 0, width, self.OVERHEAD_BAR_HEIGHT)
            start.midbottom = (on_screen.centerx, on_screen.top - self.OVERHEAD_BAR_GAP)
            spots = ((column * (width + 3), -row * (self.OVERHEAD_BAR_HEIGHT + 2))
                     for row in range(len(shown) + 1) for column in (0, -1, 1))
            for dx, dy in spots:
                bar = start.move(dx, dy)
                if bar.collidelist(placed) == -1:
                    break
            placed.append(bar)
            ally = npc in self.combat.heroes
            fraction = max(0, min(1, npc.hp / npc.max_hp)) if npc.max_hp else 0
            pygame.draw.rect(screen, (25, 25, 32), bar)
            if fraction > 0:
                pygame.draw.rect(screen, self.ALLY_COLOR if ally else self.ENEMY_COLOR,
                                 (bar.x, bar.y, max(1, round(bar.width * fraction)), bar.height))
            if npc.powered_up:
                pygame.draw.rect(screen, self.SUPER_COLOR, bar.inflate(2, 2), 1)
        return placed
