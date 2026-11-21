"""The fight's controls as actions: what the player wants this frame,
whichever of the keyboard, the touch screen or a controller says it.

The game reads a FightInput once per frame (see Game.handle_input) instead
of asking each device about each button. Each device has a table from an
action to its keys or buttons (KEYS, PAD_BUTTONS; the touch buttons are
named after the actions). A player can change them in user_settings.json
(see settings.py), for instance:

    "controls": {"keys": {"attack": ["j"], "guard": ["k", "left shift"]},
                 "pad": {"special": ["rb"]}}

The menus keep reading key presses (the controller's become keys there, see
scenes.py): arrows, Enter and Escape mean the same on every screen.
"""

from dataclasses import dataclass, field

import pygame

# Actions that happen once per press
PRESS_ACTIONS = ("attack", "special", "super", "tech_prev", "tech_next", "form_prev", "form_next", "talk")
# Actions that last while held
HOLD_ACTIONS = ("guard", "run", "special")

KEYS = {
    "attack": (pygame.K_a,),
    "special": (pygame.K_d,),
    "super": (pygame.K_s,),
    "tech_prev": (pygame.K_q,),
    "tech_next": (pygame.K_e,),
    "form_prev": (pygame.K_z,),
    "form_next": (pygame.K_x,),
    "talk": (pygame.K_t,),
    "guard": (pygame.K_f,),
    "run": (pygame.K_SPACE,),
}
MOVE_KEYS = {"left": (pygame.K_LEFT,), "right": (pygame.K_RIGHT,), "up": (pygame.K_UP,), "down": (pygame.K_DOWN,)}

# Controller buttons (gamepad.py's names), laid out for an Xbox-style pad
# such as the ROG Ally's
PAD_BUTTONS = {
    "attack": ("a",),
    "special": ("x",),
    "super": ("y",),
    "tech_prev": ("lb",),
    "tech_next": ("rb",),
    "form_next": ("rt",),
    "talk": ("view",),
    "guard": ("b",),
    "run": ("lt",),
}


@dataclass
class FightInput:
    """One frame of the player's intentions."""
    move: tuple = (0.0, 0.0)
    pressed: set = field(default_factory=set)
    held: set = field(default_factory=set)

    def __contains__(self, action):
        return action in self.pressed

    def holds(self, action):
        return action in self.held


def _key_codes(names):
    codes = []
    for name in names if isinstance(names, (list, tuple)) else [names]:
        try:
            codes.append(pygame.key.key_code(str(name)))
        except (ValueError, pygame.error):
            pass  # an unknown key name is ignored
    return tuple(codes)


class Controls:
    """The tables in use: the defaults, with the player's changes."""

    def __init__(self, overrides=None):
        overrides = overrides if isinstance(overrides, dict) else {}
        self.keys = dict(KEYS)
        for action, names in (overrides.get("keys") or {}).items():
            codes = _key_codes(names)
            if action in self.keys and codes:
                self.keys[action] = codes
        self.pad_buttons = dict(PAD_BUTTONS)
        for action, buttons in (overrides.get("pad") or {}).items():
            if action in self.pad_buttons and buttons:
                self.pad_buttons[action] = tuple(buttons if isinstance(buttons, (list, tuple)) else [buttons])

    def key_names(self, action):
        """The keys of an action, for the controls guide."""
        return [pygame.key.name(code).upper() if len(pygame.key.name(code)) == 1
                else pygame.key.name(code).title() for code in self.keys.get(action, ())]

    def read(self, events, touch, gamepad, keys=None):
        """This frame's FightInput. Touch buttons that fire once are used up
        here, as are key presses: each counts once."""
        keys = pygame.key.get_pressed() if keys is None else keys
        down = {event.key for event in events if event.type == pygame.KEYDOWN and not getattr(event, "gamepad", False)}
        frame = FightInput()
        for action in PRESS_ACTIONS:
            # Every one-shot button is consumed each frame, even if unused
            touched = action in touch.ACTIONS and touch.consume_action(action)
            if touched or down.intersection(self.keys.get(action, ())) \
                    or gamepad.pressed.intersection(self.pad_buttons.get(action, ())):
                frame.pressed.add(action)
        touch_held = {"guard": touch.blocking, "run": touch.running, "special": touch.special_held}
        for action in HOLD_ACTIONS:
            if touch_held[action] or any(keys[code] for code in self.keys.get(action, ())) \
                    or gamepad.held.intersection(self.pad_buttons.get(action, ())):
                frame.held.add(action)
        if gamepad.running:
            frame.held.add("run")  # the stick pushed to the edge

        # The analog stick wins over the controller, the controller over
        # the arrow keys
        dx, dy = touch.stick_vector
        if not (dx or dy):
            dx, dy = gamepad.move_vector
        if not (dx or dy):
            pressed = lambda direction: any(keys[code] for code in MOVE_KEYS[direction])
            dx = int(pressed("right")) - int(pressed("left"))
            dy = int(pressed("down")) - int(pressed("up"))
        frame.move = (dx, dy)
        return frame
