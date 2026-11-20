import os
import sys
import json

class Config:
    """The game's settings (Config/config.json), read once when this module
    is imported: any module can use them, in any import order. init()
    reads the file again (tests, or after it changed)."""

    CONFIG_FILE = 'Config/config.json'
    
    @classmethod
    def load_config(cls):
        # Next to the game's other files, wherever it is started from
        config_path = os.path.join(cls.root_dir(), cls.CONFIG_FILE)
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                cls.config_data = json.load(file)
        else:
            cls.config_data = {}
    
    @classmethod
    def get_config_value(cls, key, args_value=None, default_value=None):
        if args_value is not None:
            return args_value
        
        keys = key.split('.')
        data = cls.config_data
        
        for k in keys:
            if isinstance(data, dict) and k in data:
                data = data[k]
            else:
                return default_value

        return data
    
    @classmethod
    def init(cls):
        # Load application settings
        cls.load_config()
                
        # Retreive window settings
        cls.CAPTION = cls.get_config_value("caption")
        cls.WIDTH = cls.get_config_value("resolution.width")
        cls.HEIGHT = cls.get_config_value("resolution.heigth")
        # Fullscreen uses the display's own size; "resolution" is the window
        # size when fullscreen is off (or unavailable)
        cls.FULLSCREEN = bool(cls.get_config_value("fullscreen", default_value=True))
        
        # Media paths
        cls.ROOT_DIR = cls.root_dir()        
        cls.MAP_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("MAP_DIR", default_value="Graphics/maps/"))
        cls.CONFIG_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("CONFIG_DIR", default_value="Config/characters/"))
        cls.MENU_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("MENU_DIR", default_value="Graphics/menu/"))
        cls.SOUNDS_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("SOUNDS_DIR", default_value="Sounds/"))
        cls.DIALOG_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("DIALOG_DIR", default_value="Graphics/dialog/"))
        
        # Game Settings
        # Animations
        cls.CLOCK_SPEED = cls.get_config_value("CLOCK_SPEED", default_value=14)
        cls.CLOCK_LIMIT = cls.get_config_value("CLOCK_LIMIT", default_value=100)
        # Main
        cls.FPS = cls.get_config_value("FPS", default_value=60)
        
    
    @staticmethod
    def get_filename(filename: str, default=None, basename=None):
        if basename is None:
            basename = os.getcwd() if not getattr(sys, 'frozen', False) else sys.executable

        basedir = os.path.realpath(basename)
        basedir = os.path.dirname(basedir) if os.path.isfile(basedir) else basedir

        if filename is None:
            return_filename = os.path.join(basedir, default)
        else:
            return_filename = filename if os.path.isabs(filename) else os.path.join(basedir, filename)
            
        return os.path.normpath(return_filename)
    
    @staticmethod
    def root_dir():
        """The game's folder (Config/, Graphics/, Sounds/...): the project
        folder, or in a PyInstaller build (Windows) the folder it unpacks
        its data to."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            return sys._MEIPASS
        current_file_path = os.path.abspath(__file__)
        return os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))


# Loaded on import (see the class docstring)
Config.init()
