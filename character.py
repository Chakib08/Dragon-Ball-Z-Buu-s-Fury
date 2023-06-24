import pygame
from animation import Animation

class Character(Animation):
    def __init__(self, pos_x, pos_y, img_x, img_y, area_width, area_height, charac_img, size, background):
        super().__init__()
        
        self.charac_img = charac_img
        self.size = size
        self.background = background
        
        self.img_coor = [img_x, img_y]
        self.area = [area_width, area_height]
        
        # Load character image       
        self.sprit_sheet = pygame.image.load(self.charac_img)
        self.image = self.get_img(self.img_coor[0], self.img_coor[1], self.area[0], self.area[1], self.size)
        self.image.set_colorkey(self.background)
        self.imageIdx = 0
        self.images = []
        self.rect = self.image.get_rect()
        self.position = [pos_x, pos_y]
        
    def update(self):
        self.rect.topleft = self.position
        
    def get_img(self, x, y, area_width, area_height, size):
        
        # ROI from loaded image
        img = pygame.Surface(size)
        img.blit(self.sprit_sheet, (0, 0), (x, y, area_width, area_height))
        
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
