from pathlib import Path

class PathManager:
    def __init__(self, directory = Path(__file__).resolve().parent):
        self.directory = directory
        if not self.directory.exists() or not self.directory.is_dir():
            raise ValueError(f"The directory {directory} does not exist or is not a directory.")

    def custom_path(self, path):
        return self.directory / path
    
    # Maps
    def map_path(self, map_path):
        return self.directory.parent / f"Graphics/maps/{map_path}.tmx"

    # Assets Config JSON
    def character_json_path(self, character_name):
        return self.directory.parent / f"Config/{character_name}/Base/{character_name}.json"
    
    # Menu
    def menu_image_path(self, image_name):
        return self.directory.parent / f"Graphics/menu/{image_name}"
    
    # Music theme
    def soundtrack(self, name):
        return self.directory.parent / f"Sounds/{name}.wav"
        
    
    
    
    

