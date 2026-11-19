import pygame

from taps import tap_position


class QuitPrompt:
    """Quit button (top-right corner) and its "Quit game?" confirmation.

    Escape, the Android back button or a tap on the corner button opens the
    confirmation; nothing closes the game without a second, explicit answer.
    While playing it also offers to go back to the main menu instead (M).
    """

    OPEN_KEYS = (pygame.K_ESCAPE, pygame.K_AC_BACK)
    YES_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_y)
    NO_KEYS = (pygame.K_ESCAPE, pygame.K_AC_BACK, pygame.K_n)
    MENU_KEYS = (pygame.K_m,)

    def __init__(self, screen_size):
        self.screen_size = screen_size
        self.is_open = False
        self.confirmed = False
        # "Main menu" chosen (only offered while menu_available)
        self.to_menu = False
        self.menu_available = False

        shortest = min(screen_size)
        # Top-right: clear of the HP/KI bars (top-left) and the touch controls
        # (bottom corners), and where a close button is expected
        self.radius = max(22, int(shortest * 0.034))
        margin = self.radius // 2
        self.button_center = (screen_size[0] - margin - self.radius, margin + self.radius)

        panel_width = min(screen_size[0] - 40, max(360, int(shortest * 0.6)))
        panel_height = max(190, int(shortest * 0.26))
        self.panel = pygame.Rect(0, 0, panel_width, panel_height)
        self.panel.center = (screen_size[0] // 2, screen_size[1] // 2)
        button_width = int(panel_width * 0.36)
        button_height = max(52, int(panel_height * 0.3))
        button_y = self.panel.bottom - button_height - int(panel_height * 0.12)
        self.yes_rect = pygame.Rect(0, button_y, button_width, button_height)
        self.no_rect = pygame.Rect(0, button_y, button_width, button_height)
        self.yes_rect.centerx = self.panel.left + panel_width * 0.27
        self.no_rect.centerx = self.panel.left + panel_width * 0.73
        # With a "Main menu" button: three narrower buttons
        third = int(panel_width * 0.28)
        self.menu_rect = pygame.Rect(0, button_y, third, button_height)
        self.menu_rect.centerx = self.panel.left + panel_width * 0.5
        self._wide = (self.yes_rect.copy(), self.no_rect.copy())
        self._narrow = (pygame.Rect(0, button_y, third, button_height), pygame.Rect(0, button_y, third, button_height))
        self._narrow[0].centerx = self.panel.left + panel_width * 0.18
        self._narrow[1].centerx = self.panel.left + panel_width * 0.82

        self.title_font = pygame.font.Font(None, max(36, int(panel_height * 0.24)))
        self.button_font = pygame.font.Font(None, max(30, int(button_height * 0.55)))
        self.shade = pygame.Surface(screen_size, pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 150))
        self.button_surface = self._make_button_surface()

    def _make_button_surface(self):
        radius = self.radius
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surface, (25, 30, 45, 145), (radius, radius), radius)
        pygame.draw.circle(surface, (245, 245, 245, 200), (radius, radius), radius, 2)
        arm = int(radius * 0.38)
        width = max(3, radius // 7)
        for dx in (-1, 1):
            pygame.draw.line(
                surface,
                (255, 255, 255),
                (radius - arm * dx, radius - arm),
                (radius + arm * dx, radius + arm),
                width,
            )
        return surface

    def _tap_position(self, event):
        return tap_position(event, self.screen_size)

    def _on_button(self, position):
        dx = position[0] - self.button_center[0]
        dy = position[1] - self.button_center[1]
        # A little larger than drawn: easier to hit with a thumb
        return dx * dx + dy * dy <= (self.radius * 1.3) ** 2

    def _layout(self):
        """Yes and No, with Main menu between them while it is offered."""
        self.yes_rect, self.no_rect = (r.copy() for r in (self._narrow if self.menu_available else self._wide))

    def process(self, events, escape_opens=True, menu_available=False):
        """Handle the quit keys/taps and return the events the game may use.

        While the confirmation is open the game gets no input at all (only
        window events such as QUIT pass through). menu_available: offer
        "Main menu" too (sets to_menu when chosen, and closes).
        """
        self.menu_available = menu_available
        self._layout()
        remaining = []
        for event in events:
            position = self._tap_position(event)
            if self.is_open:
                if event.type == pygame.KEYDOWN:
                    if event.key in self.YES_KEYS:
                        self.confirmed = True
                    elif menu_available and event.key in self.MENU_KEYS:
                        self.to_menu = True
                        self.is_open = False
                    elif event.key in self.NO_KEYS:
                        self.is_open = False
                elif position is not None:
                    if self.yes_rect.collidepoint(position):
                        self.confirmed = True
                    elif menu_available and self.menu_rect.collidepoint(position):
                        self.to_menu = True
                        self.is_open = False
                    elif self.no_rect.collidepoint(position):
                        self.is_open = False
                elif event.type == pygame.QUIT:
                    remaining.append(event)
                continue

            if position is not None and self._on_button(position):
                self.is_open = True
            elif escape_opens and event.type == pygame.KEYDOWN and event.key in self.OPEN_KEYS:
                self.is_open = True
            else:
                remaining.append(event)
        return remaining

    def draw(self, screen):
        screen.blit(
            self.button_surface,
            (self.button_center[0] - self.radius, self.button_center[1] - self.radius),
        )
        if not self.is_open:
            return

        screen.blit(self.shade, (0, 0))
        pygame.draw.rect(screen, (25, 30, 45), self.panel, border_radius=14)
        pygame.draw.rect(screen, (245, 245, 245), self.panel, 3, border_radius=14)
        title = self.title_font.render("Quit game?", True, (255, 230, 120))
        screen.blit(title, title.get_rect(center=(self.panel.centerx, self.panel.top + self.panel.height * 0.27)))
        buttons = [(self.yes_rect, "Quit" if self.menu_available else "Yes", (200, 60, 60)),
                   (self.no_rect, "No", (60, 110, 190))]
        if self.menu_available:
            buttons.insert(1, (self.menu_rect, "Main menu", (50, 130, 70)))
        for rect, label, color in buttons:
            pygame.draw.rect(screen, color, rect, border_radius=10)
            pygame.draw.rect(screen, (245, 245, 245), rect, 2, border_radius=10)
            text = self.button_font.render(label, True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=rect.center))
