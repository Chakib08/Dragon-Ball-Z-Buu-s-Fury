"""The playable characters (Config/roster.json): their order on the
character screens, the name shown for each, and the name of a power-up form
when it is not a Super Saiyan one (Piccolo without his weights).

Only the characters whose sprite sheets are installed are offered (setup.sh
downloads them), so a missing sheet never breaks a screen.
"""

import json
import os

from animation import SpriteForm
from pathmanager import PathManager
from utils.config import Config

_entries = None


def _load():
    global _entries
    if _entries is None:
        try:
            with open(os.path.join(Config.ROOT_DIR, "Config", "roster.json")) as file:
                _entries = [entry for entry in json.load(file)["characters"] if entry.get("id")]
        except (OSError, ValueError, KeyError):
            _entries = []
    return _entries


def installed(name):
    """Whether the character's sheets are there (one form is enough)."""
    for form in ("base", "ssj", "ssj2", "ssj3"):
        try:
            path = PathManager.character_json_path(name, form)
        except ValueError:
            return False
        if os.path.exists(path) and SpriteForm.sheet_exists(path):
            return True
    return False


def characters():
    """The playable characters' ids, in screen order."""
    return tuple(entry["id"] for entry in _load() if installed(entry["id"]))


def display_name(name):
    """"Android 17" for android17; an unlisted id made readable."""
    for entry in _load():
        if entry["id"] == name:
            return entry.get("name") or name
    return str(name).replace("_", " ").title()


def level_name(name, form, default):
    """What a power-up form is called (default: the Super Saiyan level)."""
    for entry in _load():
        if entry["id"] == name:
            return entry.get("levels", {}).get(form, default)
    return default
