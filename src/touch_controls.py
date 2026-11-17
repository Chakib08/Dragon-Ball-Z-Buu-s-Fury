import math
import os

import pygame

from utils.config import Config


class TouchControls:
    """On-screen controls: an analog stick (bottom left) and same-size action
    buttons arranged around the bottom-right corner."""

    # Buttons that fire once per press (block is held instead)
    ACTIONS = ("attack", "special", "super")
    # Text labels; attack and block show a sword and a shield instead
    LABELS = {"special": "KI", "super": "SSJ"}
    ICONS = ("attack", "block")
    # Artwork for some buttons (Graphics/buttons); the others are drawn
    IMAGES = {
        "attack": "dbz_auto.png",
        "block": "dbz_gard.png",
        "super": "dbz_transform.png",
        "special": "dbz_blast.png",
    }
    # Every button has this radius, as a share of the button size
    BUTTON_RADIUS = 0.62

    # Stick travel (0 to 1) below which it does nothing, and above which the
    # character runs instead of walking
    DEAD_ZONE = 0.2
    RUN_THRESHOLD = 0.85

    def __init__(self, screen_size):
        self.screen_size = screen_size
        shortest = min(screen_size)
        self.button_size = max(60, min(150, int(shortest * 0.14)))
        self.buttons = self._make_buttons()

        size = self.button_size
        self.stick_radius = size * 1.25
        self.stick_center = (size * 2.0, screen_size[1] - size * 2.0)
        # A touch this close to the stick grabs it, so it is easy to find
        self.stick_grab_radius = self.stick_radius * 1.6
        self.stick_pointer = None
        self.stick_position = self.stick_center

        self.pointers = {}
        self.pressed_actions = set()
        self.font = pygame.font.Font(None, max(30, int(size * 0.6)))
        self.small_font = pygame.font.Font(None, max(22, int(size * 0.4)))
        self._button_art = {}
        self.button_surfaces = {
            control: (
                self._make_button_surface(control, False),
                self._make_button_surface(control, True),
            )
            for control in self.buttons
        }
        self.stick_base = self._make_stick_base()
        self.stick_knob = self._make_stick_knob()

    def _make_buttons(self):
        width, height = self.screen_size
        size = self.button_size
        # A 2 x 2 grid in the corner, attack where the thumb rests:
        #     super    special
        #     block    attack
        radius = size * self.BUTTON_RADIUS
        pitch = radius * 2 + size * 0.2
        right = width - size * 0.3 - radius
        bottom = height - size * 0.3 - radius
        return {
            "super": (right - pitch, bottom - pitch),
            "special": (right, bottom - pitch),
            "block": (right - pitch, bottom),
            "attack": (right, bottom),
        }

    def radius(self, control):
        return self.button_size * self.BUTTON_RADIUS

    # ---- State ------------------------------------------------------------------
    @property
    def stick_vector(self):
        """Stick deflection, each axis from -1 to 1 (0, 0 inside the dead zone)."""
        if self.stick_pointer is None:
            return 0.0, 0.0
        dx = (self.stick_position[0] - self.stick_center[0]) / self.stick_radius
        dy = (self.stick_position[1] - self.stick_center[1]) / self.stick_radius
        if math.hypot(dx, dy) < self.DEAD_ZONE:
            return 0.0, 0.0
        return dx, dy

    @property
    def stick_strength(self):
        return min(1.0, math.hypot(*self.stick_vector))

    @property
    def running(self):
        return self.stick_strength >= self.RUN_THRESHOLD

    @property
    def attacking(self):
        return "attack" in self.pointers.values()

    @property
    def blocking(self):
        return "block" in self.pointers.values()

    def clear(self):
        self.pointers.clear()
        self.pressed_actions.clear()
        self.stick_pointer = None
        self.stick_position = self.stick_center

    # ---- Drawing helpers ------------------------------------------------------------
    def _make_button_surface(self, control, pressed):
        image = self._load_button_image(control, pressed)
        if image is not None:
            return image
        radius = int(self.radius(control))
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        color = (245, 180, 55, 200) if pressed else (25, 30, 45, 150)
        pygame.draw.circle(surface, color, (radius, radius), radius)
        pygame.draw.circle(surface, (245, 245, 245, 210), (radius, radius), radius, 3)

        if control == "attack":
            self._draw_sword(surface, radius)
        elif control == "block":
            self._draw_shield(surface, radius)
        else:
            label = self.LABELS[control]
            font = self.font if len(label) == 1 else self.small_font
            text = font.render(label, True, (255, 255, 255))
            surface.blit(text, text.get_rect(center=(radius, radius)))
        return surface

    def _load_button_image(self, control, pressed):
        """The button's artwork cut to a circle, or None to draw it instead."""
        name = self.IMAGES.get(control)
        if name is None:
            return None
        path = os.path.join(Config.ROOT_DIR, "Graphics", "buttons", name)
        if not os.path.exists(path):
            return None
        diameter = int(self.radius(control)) * 2
        # Loaded and scaled once, shared by the normal and pressed looks
        art = self._button_art.get(control)
        if art is None:
            art = pygame.image.load(path)
            if pygame.display.get_surface() is not None:
                art = art.convert_alpha()
            art = self._button_art[control] = pygame.transform.smoothscale(art, (diameter, diameter))
        surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        surface.blit(art, (0, 0))
        # Keep only the disc: some artwork has a square black background
        mask = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
        pygame.draw.circle(mask, (255, 255, 255, 255), (diameter // 2, diameter // 2), diameter // 2)
        surface.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        if pressed:
            # Darker while held, so the press is visible
            surface.fill((170, 170, 170, 255), special_flags=pygame.BLEND_RGBA_MULT)
        return surface

    @staticmethod
    def _draw_sword(surface, radius):
        """A sword pointing up and to the right."""
        white, edge = (255, 255, 255), (40, 45, 60)
        unit = radius / 8.5

        def point(x, y):
            # x runs along the blade (towards the top right), y across it
            diagonal = 0.7071
            return (
                radius + (x + y) * diagonal * unit,
                radius + (-x + y) * diagonal * unit,
            )

        blade = [point(-2.5, -0.9), point(5.2, -0.9), point(6.6, 0), point(5.2, 0.9), point(-2.5, 0.9)]
        guard = [point(-2.5, -3), point(-1.6, -3), point(-1.6, 3), point(-2.5, 3)]
        grip = [point(-5.6, -0.6), point(-2.5, -0.6), point(-2.5, 0.6), point(-5.6, 0.6)]
        for shape in (blade, guard, grip):
            pygame.draw.polygon(surface, white, shape)
            pygame.draw.polygon(surface, edge, shape, max(1, int(unit / 2)))
        pygame.draw.circle(surface, white, point(-6.3, 0), max(2, int(unit * 1.1)))

    @staticmethod
    def _draw_shield(surface, radius):
        """A heater shield with a cross."""
        white, edge = (255, 255, 255), (40, 45, 60)
        unit = radius / 10
        cx = cy = radius

        def point(x, y):
            return (cx + x * unit, cy + y * unit)

        outline = [point(-5, -5.5), point(5, -5.5), point(5, 0), point(3.5, 3.6),
                   point(0, 6.2), point(-3.5, 3.6), point(-5, 0)]
        pygame.draw.polygon(surface, white, outline)
        pygame.draw.polygon(surface, edge, outline, max(1, int(unit / 2)))
        width = max(2, int(unit * 1.2))
        pygame.draw.line(surface, edge, point(0, -4.6), point(0, 4.8), width)
        pygame.draw.line(surface, edge, point(-4.1, -1.2), point(4.1, -1.2), width)

    def _make_stick_base(self):
        radius = int(self.stick_radius)
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surface, (25, 30, 45, 110), (radius, radius), radius)
        pygame.draw.circle(surface, (245, 245, 245, 160), (radius, radius), radius, 3)
        # Inner ring: past it the character runs
        pygame.draw.circle(
            surface, (245, 245, 245, 70), (radius, radius), int(radius * self.RUN_THRESHOLD), 2
        )
        return surface

    def _make_stick_knob(self):
        radius = int(self.stick_radius * 0.45)
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surface, (235, 235, 235, 190), (radius, radius), radius)
        pygame.draw.circle(surface, (255, 255, 255, 230), (radius, radius), radius, 3)
        return surface

    # ---- Input ------------------------------------------------------------------
    def _control_at(self, position):
        for control, center in self.buttons.items():
            # Slightly larger than drawn: easier to hit with a thumb
            reach = self.radius(control) * 1.1
            if (position[0] - center[0]) ** 2 + (position[1] - center[1]) ** 2 <= reach ** 2:
                return control
        return None

    def _on_stick(self, position):
        return math.dist(position, self.stick_center) <= self.stick_grab_radius

    def _move_stick(self, position):
        # The knob follows the finger but stays inside the base
        dx = position[0] - self.stick_center[0]
        dy = position[1] - self.stick_center[1]
        distance = math.hypot(dx, dy)
        if distance > self.stick_radius:
            dx, dy = dx / distance * self.stick_radius, dy / distance * self.stick_radius
        self.stick_position = (self.stick_center[0] + dx, self.stick_center[1] + dy)

    def handle_event(self, event):
        pointer = position = None
        is_down = is_up = False

        if event.type in (pygame.FINGERDOWN, pygame.FINGERMOTION, pygame.FINGERUP):
            pointer = ("finger", event.finger_id)
            position = (event.x * self.screen_size[0], event.y * self.screen_size[1])
            is_down = event.type == pygame.FINGERDOWN
            is_up = event.type == pygame.FINGERUP
        elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP) and event.button == 1:
            pointer = ("mouse", 0)
            position = event.pos
            is_down = event.type == pygame.MOUSEBUTTONDOWN
            is_up = event.type == pygame.MOUSEBUTTONUP
        elif event.type == pygame.MOUSEMOTION and event.buttons[0]:
            pointer = ("mouse", 0)
            position = event.pos
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.clear()
            return

        if pointer is None:
            return

        if is_up:
            self.pointers.pop(pointer, None)
            if pointer == self.stick_pointer:
                self.stick_pointer = None
                self.stick_position = self.stick_center
            return

        # The finger holding the stick keeps it wherever it goes
        if pointer == self.stick_pointer:
            self._move_stick(position)
            return
        if is_down and self.stick_pointer is None and self._on_stick(position):
            self.stick_pointer = pointer
            self._move_stick(position)
            return

        control = self._control_at(position)
        previous = self.pointers.get(pointer)
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
        base = self.stick_base
        screen.blit(base, (self.stick_center[0] - base.get_width() / 2,
                           self.stick_center[1] - base.get_height() / 2))
        knob = self.stick_knob
        screen.blit(knob, (self.stick_position[0] - knob.get_width() / 2,
                           self.stick_position[1] - knob.get_height() / 2))
        for control, center in self.buttons.items():
            is_pressed = control in self.pointers.values()
            surface = self.button_surfaces[control][int(is_pressed)]
            screen.blit(surface, (center[0] - surface.get_width() / 2, center[1] - surface.get_height() / 2))
