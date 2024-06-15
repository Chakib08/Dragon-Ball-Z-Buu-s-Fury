import pygame
import json
from pathlib import Path
              
class Animation(pygame.sprite.Sprite):
    def __init__(self, json_file):
        super().__init__()
        self.character_name = self.parse_data(json_file, "Character")
        
        parent_dir = Path(__file__).resolve().parent.parent
        self.sprit_sheet =  pygame.image.load(parent_dir / self.parse_data(json_file, "Image path"))
        self.animations = self.parse_data(json_file, "Animations")
        self.current_animation_index = 0
        self.animation_name = "IDLE Down"
        self.image = self.get_image_by_animation_name(self.animation_name)
        self.images = []
        self.rect = self.image.get_rect()

    def parse_data(self, json_file, key):
        with open(json_file) as file:
            data = json.load(file)
        return data[key]
    
    def get_animation_by_name(self, animation_name):
        for animation in self.animations:
            if animation["AnimationName"] == animation_name:
                return animation
        return None
            
    def get_image_by_animation_name(self, animation_name):
        animation = self.get_animation_by_name(animation_name)
        x = animation["x"]
        y = animation["y"]
        area_width = animation["Area Width"]
        area_height = animation["Area Height"]
        size = (animation["Size"]["Width"], animation["Size"]["Height"])
        bg = (animation["Background"]["R"], animation["Background"]["G"], animation["Background"]["B"])

        img = pygame.Surface(size)
        img.blit(self.sprit_sheet, (0, 0), (x, y, area_width, area_height))
        img.set_colorkey(bg)
        return img
    
    def animate(self, animation_macro, animation_nbr):
        self.images = []
        for i in range(animation_nbr):
            self.images.append(self.get_image_by_animation_name(animation_macro + " " + str(i)))

        self.image = self.images[self.current_animation_index]
        if "Left" in animation_macro:
            self.image = pygame.transform.flip(self.image, True, False)
        self.current_animation_index += 1

        if(self.current_animation_index == len(self.images)):
            self.current_animation_index = 0
        pygame.time.delay(100)
