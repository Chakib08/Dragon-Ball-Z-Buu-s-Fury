import os
import sys
import yaml
import pandas as pd

class Config:
    CONFIG_FILE = 'Config/config.yaml'
    
    @classmethod
    def load_config(cls):
        config_path = cls.get_filename(cls.CONFIG_FILE)
        if os.path.exists(config_path):
            with open(config_path, 'r') as file:
                cls.config_data = yaml.safe_load(file)
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
        # Load config.yaml 
        cls.load_config()
                
        # Retreive window settings
        cls.CAPTION = cls.get_config_value("caption")
        cls.WIDTH = cls.get_config_value("resolution.width")
        cls.HEIGHT = cls.get_config_value("resolution.heigth")
        
        # Media paths
        cls.ROOT_DIR = cls.root_dir()        
        cls.MAP_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("MAP_DIR"))
        cls.CONFIG_DIR = os.path.join(cls.ROOT_DIR,cls.get_config_value("CONFIG_DIR"))
        cls.MENU_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("MENU_DIR"))
        cls.SOUNDS_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("SOUNDS_DIR"))
        cls.DIALOG_DIR = os.path.join(cls.ROOT_DIR, cls.get_config_value("DIALOG_DIR"))  
    
    @staticmethod
    def get_filename(filename: str, default=None, basename=None):
        if basename is None:
            basename = os.getcwd() if not getattr(sys, 'frozen', False) else sys.executable

        basedir = os.path.realpath(basename)
        basedir = os.path.dirname(basedir) if os.path.isfile(basedir) else basedir

        if filename is None or pd.isna(filename):
            return_filename = os.path.join(basedir, default)
        else:
            return_filename = filename if os.path.isabs(filename) else os.path.join(basedir, filename)
            
        return os.path.normpath(return_filename)
    
    @staticmethod
    def root_dir():
        current_file_path = os.path.abspath(__file__)
        return os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

