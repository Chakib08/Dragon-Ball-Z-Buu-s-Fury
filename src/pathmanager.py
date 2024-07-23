from pathlib import Path



class PathManager: 
    DEFAULT_DIR_PATH = Path(__file__).resolve().parent.parent
    
    # Maps
    @classmethod
    def map_path(cls, map):
        return cls.DEFAULT_DIR_PATH / f"Graphics/maps/{map}.tmx"

    # Assets Config JSON
    @classmethod
    def character_json_path(cls, character_name):
        return cls.DEFAULT_DIR_PATH  / f"Config/{character_name}/Base/{character_name}.json"
    
    # Menu
    @classmethod
    def menu_image_path(cls, image_name):
        return cls.DEFAULT_DIR_PATH  / f"Graphics/menu/{image_name}"
    
    # Music theme
    @classmethod
    def soundtrack(cls, name):
        return cls.DEFAULT_DIR_PATH  / f"Sounds/{name}.wav"
    
    # Dialog
    @classmethod
    def dialogFile(cls, filename):
        return cls.DEFAULT_DIR_PATH / f"Graphics/dialog/{filename}"
    
    @classmethod
    def dir(cls):
        return cls.DEFAULT_DIR_PATH
        
    
    
    
    

