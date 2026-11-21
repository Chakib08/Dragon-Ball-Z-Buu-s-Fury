import os
from utils.config import Config


class PathManager:    
    # Maps
    @classmethod
    def map_path(cls, map_name):
        if Config.MAP_DIR and os.path.exists(Config.MAP_DIR):
            path = os.path.join(Config.MAP_DIR, f"{map_name}.tmx")
            if not os.path.exists(path):
                # An arena built from the dbz-assets pictures (arenas.py)
                import arenas
                built = arenas.built_path(map_name)
                if built:
                    return built
            return path
        else:
            raise ValueError("MAP_DIR is invalid or does not exist")
        
    # Assets Config JSON
    @classmethod
    def character_json_path(cls, character_name, state):
        if Config.CONFIG_DIR and os.path.exists(Config.CONFIG_DIR):
            return os.path.join(Config.CONFIG_DIR, f"{character_name}/{state}.json")
        else:
            raise ValueError("CONFIG_DIR is invalid or does not exist")

    # Menu
    @classmethod
    def menu_image_path(cls, image_name):
        if Config.MENU_DIR and os.path.exists(Config.MENU_DIR):
            return os.path.join(Config.MENU_DIR, image_name)
        else:
            raise ValueError("MENU_DIR is invalid or does not exist")

    # Music theme
    @classmethod
    def soundtrack(cls, name):
        """A music file of Sounds/ by name: the .ogg when there is one (much
        smaller), else the .wav."""
        if Config.SOUNDS_DIR and os.path.exists(Config.SOUNDS_DIR):
            ogg = os.path.join(Config.SOUNDS_DIR, f"{name}.ogg")
            return ogg if os.path.exists(ogg) else os.path.join(Config.SOUNDS_DIR, f"{name}.wav")
        else:
            raise ValueError("SOUNDS_DIR is invalid or does not exist")

    # Dialog
    @classmethod
    def dialog_file(cls, filename):
        if Config.DIALOG_DIR and os.path.exists(Config.DIALOG_DIR):
            return os.path.join(Config.DIALOG_DIR, filename)
        else:
            raise ValueError("DIALOG_DIR is invalid or does not exist")
        
    
    
    
    

