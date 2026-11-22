"""The maps fights can happen on (Config/arenas.json): Goku's home, built
into the game, and the arenas tools/build_arenas.py cuts from the map
pictures of dbz-assets (setup.sh builds them in Graphics/assets/arenas).
Only the arenas that are built are offered.
"""

import json
import os

import pygame

from utils.config import Config

DEFAULT = "map"
_entries = None
_thumbnails = {}


def arenas_dir():
    return os.path.join(Config.ROOT_DIR, "Graphics", "assets", "arenas")


def _load():
    global _entries
    if _entries is None:
        try:
            with open(os.path.join(Config.ROOT_DIR, "Config", "arenas.json")) as file:
                _entries = [entry for entry in json.load(file)["arenas"] if entry.get("id")]
        except (OSError, ValueError, KeyError):
            _entries = [{"id": DEFAULT, "name": "Goku's Home", "builtin": True}]
    return _entries


def built_path(name):
    """The .tmx of a built arena, or None."""
    path = os.path.join(arenas_dir(), f"{name}.tmx")
    return path if os.path.exists(path) else None


def available():
    """The ids of the arenas one can fight on, in the screen's order."""
    return tuple(entry["id"] for entry in _load() if entry.get("builtin") or built_path(entry["id"]))


def music(arena):
    """The arena's own soundtrack (a name under Sounds/, see
    PathManager.soundtrack), or None."""
    for entry in _load():
        if entry["id"] == arena:
            return entry.get("music")
    return None


def name(arena):
    for entry in _load():
        if entry["id"] == arena:
            return entry.get("name", arena)
    return str(arena).replace("_", " ").title()


def thumbnail(arena):
    """A small picture of the arena (a shared surface), or None."""
    if arena in _thumbnails:
        return _thumbnails[arena]
    image = None
    path = os.path.join(arenas_dir(), f"{arena}_thumb.png")
    try:
        if os.path.exists(path):
            image = pygame.image.load(path)
        elif arena == DEFAULT:
            image = _render_builtin()
    except (pygame.error, OSError, ValueError):
        image = None
    _thumbnails[arena] = image
    return image


def _render_builtin():
    """Goku's home, drawn small from its own map."""
    import pytmx
    from pathmanager import PathManager
    data = pytmx.load_pygame(PathManager.map_path(DEFAULT))
    picture = pygame.Surface((data.width * data.tilewidth, data.height * data.tileheight))
    for layer in data.visible_layers:
        if isinstance(layer, pytmx.TiledTileLayer):
            for x, y, image in layer.tiles():
                picture.blit(image, (x * data.tilewidth, y * data.tileheight))
    ratio = min(240 / picture.get_width(), 160 / picture.get_height())
    return pygame.transform.smoothscale(picture, (round(picture.get_width() * ratio),
                                                  round(picture.get_height() * ratio)))
