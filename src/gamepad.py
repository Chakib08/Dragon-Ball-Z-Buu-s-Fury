"""Game controllers: the ROG Ally's built-in controls, Xbox, PlayStation or
Switch controllers (SDL's game controller API gives them all the same
layout, named after the Xbox one).

Polled once per frame (update): which buttons are held, which were just
pressed, and where the left stick points. The game reads the held ones
(moving, guarding, charging, running) and turns presses into the keys it
already understands (see Game.gamepad_key_events), so every menu works with
it as with a keyboard.

Without pygame's controller module (pygame._sdl2.controller, left out of
some mobile builds) there is simply no controller.
"""

import math

import pygame

try:
    from pygame._sdl2 import controller as sdl_controller
except ImportError:  # pragma: no cover (builds without pygame._sdl2)
    sdl_controller = None

# Our names for the controller's buttons (A B X Y as on an Xbox pad and the
# ROG Ally; View and Menu are SDL's BACK and START)
BUTTONS = {
    "a": "CONTROLLER_BUTTON_A",
    "b": "CONTROLLER_BUTTON_B",
    "x": "CONTROLLER_BUTTON_X",
    "y": "CONTROLLER_BUTTON_Y",
    "lb": "CONTROLLER_BUTTON_LEFTSHOULDER",
    "rb": "CONTROLLER_BUTTON_RIGHTSHOULDER",
    "view": "CONTROLLER_BUTTON_BACK",
    "menu": "CONTROLLER_BUTTON_START",
    "ls": "CONTROLLER_BUTTON_LEFTSTICK",
    "rs": "CONTROLLER_BUTTON_RIGHTSTICK",
    "up": "CONTROLLER_BUTTON_DPAD_UP",
    "down": "CONTROLLER_BUTTON_DPAD_DOWN",
    "left": "CONTROLLER_BUTTON_DPAD_LEFT",
    "right": "CONTROLLER_BUTTON_DPAD_RIGHT",
}
# The triggers are axes: past this, they count as pressed
TRIGGERS = {"lt": "CONTROLLER_AXIS_TRIGGERLEFT", "rt": "CONTROLLER_AXIS_TRIGGERRIGHT"}
TRIGGER_THRESHOLD = 0.5
AXIS_MAX = 32767


class Gamepad:
    # The stick ignores small movements, and counts as pushed to the edge
    # (running) past RUN_THRESHOLD
    DEADZONE = 0.25
    RUN_THRESHOLD = 0.9
    # In menus the stick moves the selection like the D-pad: once when it is
    # pushed, then again every REPEAT_MS while it stays pushed
    MENU_THRESHOLD = 0.6
    REPEAT_DELAY_MS = 400
    REPEAT_MS = 150

    def __init__(self):
        self.controllers = []
        self.held = set()
        self.pressed = set()
        self.stick = (0.0, 0.0)
        # Whether the player is using a controller (its button hints are
        # shown, the touch buttons hidden) until the screen is touched
        self.active = False
        self._stick_direction = None
        self._stick_repeat_at = 0
        if sdl_controller is not None:
            try:
                sdl_controller.init()
            except pygame.error:
                pass
        self.refresh()

    # ---- Devices ------------------------------------------------------------------
    @property
    def connected(self):
        return bool(self.controllers)

    def refresh(self):
        """Open every controller plugged in (also called when one comes or goes)."""
        self.controllers = []
        if sdl_controller is None:
            return
        try:
            for index in range(sdl_controller.get_count()):
                if sdl_controller.is_controller(index):
                    self.controllers.append(sdl_controller.Controller(index))
        except pygame.error:
            self.controllers = []
        if not self.controllers:
            self.active = False

    DEVICE_EVENTS = tuple(getattr(pygame, name) for name in (
        "CONTROLLERDEVICEADDED", "CONTROLLERDEVICEREMOVED", "JOYDEVICEADDED", "JOYDEVICEREMOVED")
        if hasattr(pygame, name))

    def handle_event(self, event):
        if event.type in self.DEVICE_EVENTS:
            self.refresh()
        elif event.type in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN):
            self.active = False  # back to the touch screen (or the mouse)

    # ---- State ----------------------------------------------------------------------
    def _read(self):
        """(buttons held, left stick) of all controllers together."""
        held = set()
        x = y = 0.0
        for pad in self.controllers:
            try:
                for name, constant in BUTTONS.items():
                    if pad.get_button(getattr(pygame, constant)):
                        held.add(name)
                for name, constant in TRIGGERS.items():
                    if pad.get_axis(getattr(pygame, constant)) / AXIS_MAX > TRIGGER_THRESHOLD:
                        held.add(name)
                px = pad.get_axis(pygame.CONTROLLER_AXIS_LEFTX) / AXIS_MAX
                py = pad.get_axis(pygame.CONTROLLER_AXIS_LEFTY) / AXIS_MAX
            except pygame.error:
                continue  # unplugged meanwhile: refreshed on its event
            if math.hypot(px, py) > math.hypot(x, y):
                x, y = px, py
        return held, (x, y)

    def update(self, now=None):
        """Read the controllers; call once per frame."""
        now = pygame.time.get_ticks() if now is None else now
        held, (x, y) = self._read()
        if math.hypot(x, y) < self.DEADZONE:
            x = y = 0.0
        self.pressed = held - self.held
        self.held = held
        self.stick = (max(-1.0, min(1.0, x)), max(-1.0, min(1.0, y)))
        self.menu_moves = self._stick_menu_moves(now)
        if self.pressed or self.stick != (0.0, 0.0):
            self.active = True

    @property
    def move_vector(self):
        """Where the player walks: the left stick, else the D-pad."""
        if self.stick != (0.0, 0.0):
            return self.stick
        dx = ("right" in self.held) - ("left" in self.held)
        dy = ("down" in self.held) - ("up" in self.held)
        return float(dx), float(dy)

    @property
    def running(self):
        return "lt" in self.held or math.hypot(*self.stick) >= self.RUN_THRESHOLD

    def _stick_menu_moves(self, now):
        """The stick as D-pad presses, for the menus."""
        x, y = self.stick
        direction = None
        if max(abs(x), abs(y)) >= self.MENU_THRESHOLD:
            if abs(x) >= abs(y):
                direction = "right" if x > 0 else "left"
            else:
                direction = "down" if y > 0 else "up"
        if direction is None:
            self._stick_direction = None
            return set()
        if direction != self._stick_direction:
            self._stick_direction = direction
            self._stick_repeat_at = now + self.REPEAT_DELAY_MS
            return {direction}
        if now >= self._stick_repeat_at:
            self._stick_repeat_at = now + self.REPEAT_MS
            return {direction}
        return set()

    menu_moves = set()

    def menu_presses(self):
        """Buttons pressed this frame, the stick counting as the D-pad."""
        return self.pressed | self.menu_moves
