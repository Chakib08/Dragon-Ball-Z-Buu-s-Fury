"""Each character's face, for the character screens: a framed 64 x 64
portrait cut from the dialog portraits sheet. Config/portraits.json says
where each one is on it (its top-left corner); a character without one
gets None (the screens then show its sprite instead).
"""

import json
import os

import pygame

from utils.config import Config

_portraits = {}
_layout = None


def _load_layout():
    global _layout
    if _layout is None:
        path = os.path.join(Config.ROOT_DIR, "Config", "portraits.json")
        try:
            with open(path) as file:
                _layout = json.load(file)
        except (OSError, ValueError):
            _layout = {}
    return _layout


def portrait(name):
    """The character's portrait (a shared surface: do not draw on it), or None."""
    if name in _portraits:
        return _portraits[name]
    layout = _load_layout()
    corner = layout.get("characters", {}).get(name)
    image = None
    if corner is not None:
        try:
            sheet = pygame.image.load(os.path.join(Config.ROOT_DIR, layout["sheet"]))
            size = int(layout.get("size", 64))
            image = sheet.subsurface(pygame.Rect(corner[0], corner[1], size, size)).copy()
            # The sheet's background shows at the frame's rounded corners
            image.set_colorkey(sheet.get_at((0, 0))[:3])
        except (pygame.error, KeyError, ValueError, TypeError, OSError):
            image = None
    _portraits[name] = image
    return image
