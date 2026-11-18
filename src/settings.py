"""Player settings that can change in the game (saved between sessions).

The file lives where the app may write: the app's private folder on Android,
the project folder elsewhere.
"""

import json
import os

from utils.config import Config

FILE_NAME = "user_settings.json"
DEFAULT_SERVER_PORT = 5050


def settings_path():
    folder = os.environ.get("ANDROID_PRIVATE") or Config.ROOT_DIR
    return os.path.join(folder, FILE_NAME)


def load():
    settings = {
        "server_host": Config.get_config_value("server.host", default_value="127.0.0.1"),
        "server_port": Config.get_config_value("server.port", default_value=DEFAULT_SERVER_PORT),
    }
    try:
        with open(settings_path()) as file:
            saved = json.load(file)
        if isinstance(saved, dict):
            settings.update(saved)
    except (OSError, ValueError):
        pass
    return settings


def save(settings):
    try:
        with open(settings_path(), "w") as file:
            json.dump(settings, file, indent=2)
    except OSError:
        pass  # not being able to remember a setting must not stop the game


def parse_address(text, default_port=DEFAULT_SERVER_PORT):
    """"host" or "host:port" -> (host, port), or None if it is not valid."""
    text = text.strip()
    if not text:
        return None
    host, _, port = text.rpartition(":") if ":" in text else (text, "", "")
    if not host:
        return None
    if not port:
        return host, default_port
    if not port.isdigit() or not 0 < int(port) < 65536:
        return None
    return host, int(port)
