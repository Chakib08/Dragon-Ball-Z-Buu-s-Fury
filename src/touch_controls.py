import pygame


class TouchControls:
    DIRECTIONS = ("up", "down", "left", "right")
    # Buttons that fire once per press
    ACTIONS = ("attack", "interact", "special", "super")
    LABELS = {"special": "KI", "super": "SSJ"}

    def __init__(self, screen_size):
        self.screen_size = screen_size
        self.button_size = max(44, min(82, int(min(screen_size) * 0.11)))
        self.buttons = self._make_buttons()
        self.pointers = {}
        self.pressed_actions = set()
        self.font = pygame.font.Font(None, max(24, self.button_size // 2))
        self.small_font = pygame.font.Font(None, max(18, self.button_size // 3))
        self.button_surfaces = {
            control: (
                self._make_button_surface(control, False),
                self._make_button_surface(control, True),
            )
            for control in self.buttons
        }

    def _make_buttons(self):
        width, height = self.screen_size
        size = self.button_size
        dpad_x, dpad_y = size * 1.75, height - size * 1.65
        return {
            "up": (dpad_x, dpad_y - size),
            "down": (dpad_x, dpad_y + size),
            "left": (dpad_x - size, dpad_y),
            "right": (dpad_x + size, dpad_y),
            "attack": (width - size * 1.35, height - size * 1.65),
            "interact": (width - size * 2.45, height - size * 0.85),
            "run": (width - size * 0.85, height - size * 0.85),
            "special": (width - size * 2.55, height - size * 2.0),
            "super": (width - size * 1.35, height - size * 2.95),
        }

    @property
    def directions(self):
        return {control for control in self.pointers.values() if control in self.DIRECTIONS}

    @property
    def running(self):
        return "run" in self.pointers.values()

    @property
    def attacking(self):
        return "attack" in self.pointers.values()

    def clear(self):
        self.pointers.clear()
        self.pressed_actions.clear()

    def _make_button_surface(self, control, pressed):
        radius = int(self.button_size * (0.63 if control == "attack" else 0.48))
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        color = (245, 180, 55, 190) if pressed else (25, 30, 45, 145)
        pygame.draw.circle(surface, color, (radius, radius), radius)
        pygame.draw.circle(surface, (245, 245, 245, 200), (radius, radius), radius, 2)

        label = self.LABELS.get(control, control[0].upper())
        font = self.font if len(label) == 1 else self.small_font
        text = font.render(label, True, (255, 255, 255))
        surface.blit(text, text.get_rect(center=(radius, radius)))
        return surface

    def _control_at(self, position):
        radius = self.button_size * 0.52
        for control, center in self.buttons.items():
            if (position[0] - center[0]) ** 2 + (position[1] - center[1]) ** 2 <= radius ** 2:
                return control
        return None

    def handle_event(self, event):
        pointer = None
        position = None
        is_down = False
        is_up = False
        is_motion = False

        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            pointer = ("finger", event.finger_id)
            position = (event.x * self.screen_size[0], event.y * self.screen_size[1])
            is_down = event.type == pygame.FINGERDOWN
            is_up = event.type == pygame.FINGERUP
            is_motion = event.type == pygame.FINGERMOTION
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and event.button == 1:
            pointer = ("mouse", 0)
            position = event.pos
            is_down = event.type == pygame.MOUSEBUTTONDOWN
            is_up = event.type == pygame.MOUSEBUTTONUP
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.clear()
            return

        if pointer is None:
            return

        if is_up:
            self.pointers.pop(pointer, None)
            return

        if is_down or is_motion:
            control = self._control_at(position)
            previous = self.pointers.get(pointer)
            if is_down or is_motion:
                if control is None:
                    self.pointers.pop(pointer, None)
                else:
                    self.pointers[pointer] = control
                    if control in self.ACTIONS and control != previous:
                        self.pressed_actions.add(control)

    def consume_action(self, action):
        if action in self.pressed_actions:
            self.pressed_actions.remove(action)
            return True
        return False

    def draw(self, screen):
        for control, center in self.buttons.items():
            is_pressed = control in self.pointers.values()
            surface = self.button_surfaces[control][int(is_pressed)]
            screen.blit(surface, (center[0] - surface.get_width() / 2, center[1] - surface.get_height() / 2))
