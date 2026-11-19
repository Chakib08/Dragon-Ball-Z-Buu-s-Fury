import pygame

from quit_prompt import draw_pad_badge
from taps import tap_position


class ResultScreen:
    """End of a story fight: lost (the player is knocked out) or won (every
    enemy is). Offers to fight again with the same team, or to go back to
    the main menu.

    Enter / R / a tap on the first button: "retry"; Esc / M / a tap on the
    second: "menu".
    """

    RETRY_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_r, pygame.K_SPACE)
    # Show the controller's buttons instead of the keyboard's (set by the game)
    gamepad_hints = False
    MENU_KEYS = (pygame.K_ESCAPE, pygame.K_AC_BACK, pygame.K_m)

    def __init__(self, screen_size, victory):
        self.screen_size = screen_size
        self.victory = victory
        shortest = min(screen_size)
        panel_width = min(screen_size[0] - 40, max(380, int(shortest * 0.7)))
        panel_height = max(200, int(shortest * 0.32))
        self.panel = pygame.Rect(0, 0, panel_width, panel_height)
        self.panel.center = (screen_size[0] // 2, screen_size[1] // 2)
        button_width = int(panel_width * 0.38)
        button_height = max(52, int(panel_height * 0.26))
        button_y = self.panel.bottom - button_height - int(panel_height * 0.12)
        self.retry_rect = pygame.Rect(0, button_y, button_width, button_height)
        self.menu_rect = pygame.Rect(0, button_y, button_width, button_height)
        self.retry_rect.centerx = self.panel.left + panel_width * 0.27
        self.menu_rect.centerx = self.panel.left + panel_width * 0.73
        self.title_font = pygame.font.Font(None, max(40, int(panel_height * 0.26)))
        self.text_font = pygame.font.Font(None, max(26, int(panel_height * 0.13)))
        self.button_font = pygame.font.Font(None, max(30, int(button_height * 0.55)))
        self.shade = pygame.Surface(screen_size, pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 160))

    @property
    def title(self):
        return "Victory!" if self.victory else "You lost..."

    @property
    def retry_label(self):
        return "Play again" if self.victory else "Retry"

    def process(self, events):
        """"retry", "menu" or None (no choice yet)."""
        for event in events:
            if event.type == pygame.KEYDOWN:
                if event.key in self.RETRY_KEYS:
                    return "retry"
                if event.key in self.MENU_KEYS:
                    return "menu"
            position = tap_position(event, self.screen_size)
            if position is not None:
                if self.retry_rect.collidepoint(position):
                    return "retry"
                if self.menu_rect.collidepoint(position):
                    return "menu"
        return None

    def draw(self, screen):
        screen.blit(self.shade, (0, 0))
        pygame.draw.rect(screen, (25, 30, 45), self.panel, border_radius=14)
        pygame.draw.rect(screen, (245, 245, 245), self.panel, 3, border_radius=14)
        color = (255, 220, 90) if self.victory else (235, 90, 80)
        title = self.title_font.render(self.title, True, color)
        screen.blit(title, title.get_rect(center=(self.panel.centerx, self.panel.top + self.panel.height * 0.22)))
        hint_text = (f"A: {self.retry_label}   B: Main menu" if self.gamepad_hints
                     else f"Enter: {self.retry_label}   Esc: Main menu")
        hint = self.text_font.render(hint_text, True, (210, 210, 220))
        screen.blit(hint, hint.get_rect(center=(self.panel.centerx, self.panel.top + self.panel.height * 0.45)))
        for rect, label, fill, pad_button in (
            (self.retry_rect, self.retry_label, (50, 130, 70), "A"),
            (self.menu_rect, "Main menu", (60, 110, 190), "B"),
        ):
            pygame.draw.rect(screen, fill, rect, border_radius=10)
            pygame.draw.rect(screen, (245, 245, 245), rect, 2, border_radius=10)
            text = self.button_font.render(label, True, (255, 255, 255))
            screen.blit(text, text.get_rect(center=rect.center))
            if self.gamepad_hints:
                draw_pad_badge(screen, pad_button, (rect.left + 4, rect.top + 2), int(rect.height * 0.3))
