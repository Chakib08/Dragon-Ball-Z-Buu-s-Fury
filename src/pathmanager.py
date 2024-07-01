from pathlib import Path

DEFAULT_DIR_PATH = Path(__file__).resolve().parent.parent

class PathManager: 
    # Maps
    @classmethod
    def map_path(self, map):
        return DEFAULT_DIR_PATH / f"Graphics/maps/{map}.tmx"

    # Assets Config JSON
    @classmethod
    def character_json_path(self, character_name):
        return DEFAULT_DIR_PATH  / f"Config/{character_name}/Base/{character_name}.json"
    
    # Menu
    @classmethod
    def menu_image_path(self, image_name):
        return DEFAULT_DIR_PATH  / f"Graphics/menu/{image_name}"
    
    # Music theme
    @classmethod
    def soundtrack(self, name):
        return DEFAULT_DIR_PATH  / f"Sounds/{name}.wav"
    @classmethod
    def dir(self):
        return DEFAULT_DIR_PATH
        
    
    
    
    

