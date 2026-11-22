"""Each character's face, for the character screens: a framed 64 x 64
portrait cut from one of the portrait sheets (setup.sh downloads them).
Config/portraits.json lists the sheets and, per character, the sheet and
the top-left corner of its portrait (a sheet with a "scale" is a sprite
sheet: its crop is enlarged); a character without one gets None
(the screens then show its sprite instead).
"""

import json
import os

import pygame

from utils.config import Config

_portraits = {}
_sheets = {}
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


def sheet(key):
    """A portrait sheet ("bf", "log2") as a surface, or None if missing."""
    if key not in _sheets:
        info = _load_layout().get("sheets", {}).get(key, {})
        try:
            _sheets[key] = pygame.image.load(os.path.join(Config.ROOT_DIR, info["path"]))
        except (pygame.error, KeyError, OSError, FileNotFoundError):
            _sheets[key] = None
    return _sheets[key]


def portrait(name):
    """The character's portrait (a shared surface: do not draw on it), or None."""
    if name in _portraits:
        return _portraits[name]
    layout = _load_layout()
    entry = layout.get("characters", {}).get(name)
    image = None
    if entry is not None:
        try:
            key, x, y = entry
            info = layout["sheets"][key]
            source = sheet(key)
            if source is not None:
                size = int(info.get("size", 64))
                image = source.subsurface(pygame.Rect(x, y, size, size)).copy()
                if info.get("transparent_corners"):
                    # The sheet's background shows at the frame's rounded corners
                    image.set_colorkey(source.get_at((0, 0))[:3])
                if info.get("scale"):
                    # A face cut from a sprite sheet (smaller: enlarged, pixel
                    # art) or a big picture (shrunk smoothly)
                    scale = float(info["scale"])
                    side = round(size * scale)
                    if scale < 1:
                        full = pygame.Surface(image.get_size(), pygame.SRCALPHA)
                        full.blit(image, (0, 0))
                        image = pygame.transform.smoothscale(full, (side, side))
                    else:
                        image = pygame.transform.scale(image, (side, side))
        except (pygame.error, KeyError, ValueError, TypeError):
            image = None
    _portraits[name] = image
    return image
