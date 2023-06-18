from typing import Any
import pygame

class Character(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y, charac_img, size, background):
        super().__init__()
        
        self.charac_img = charac_img
        self.size = size
        self.background = background
        
        # Load character image       
        self.sprit_sheet = pygame.image.load(self.charac_img)
        self.image = self.get_img(1, 2, self.size)
        self.image.set_colorkey(self.background)
        self.rect = self.image.get_rect()
        self.position = [pos_x, pos_y]
        
    def update(self):
        self.rect.topleft = self.position
        
    def get_img(self, x, y, size):
        
        # ROI from loaded image
        img = pygame.Surface(size)
        img.blit(self.sprit_sheet, (0, 0), (x, y, 32, 32))
        
        return img
    
    def move(self, side, speed):
        self.side = side
        self.speed = speed
        
        if(self.side == "right"):
            self.position[0] += self.speed

        if(self.side == "left"):
            self.position[0] -= self.speed

        if(self.side == "down"):
            self.position[1] += self.speed

        if(self.side == "up"):
            self.position[1] -= self.speed
