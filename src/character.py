from animation import Animation
from utils.config import Config
import pygame

class Character(Animation):
    def __init__(self, pos_x, pos_y, json_file):
        super().__init__(json_file)
        
        # self.hp = hp
        # self.ki = ki
        self.speed = 0
        self.position = [pos_x, pos_y]
        self.rect = self.image.get_rect()
        self.feet = pygame.Rect(0, 0, self.rect.width / 4, 4)
        self.old_position = self.position.copy()
        
    def update(self):
        self.rect.topleft = self.position
        self.feet.midbottom = self.rect.midbottom

    def move_back(self):
        self.position = self.old_position
        self.feet.midbottom = self.rect.midbottom
        #self.rect.topleft = self.rect.midbottom
    
    def move(self, side):
        self.side = side
        
        if(self.side == "Right"):
            self.position[0] += self.speed

        elif(self.side == "Left"):
            self.position[0] -= self.speed

        elif(self.side == "Down"):
            self.position[1] += self.speed

        elif(self.side == "Up"):
            self.position[1] -= self.speed      
        else:
            pass
    
    def attack():
        pass
            
    def animate(self, animation_macro, animation_nbr):
        super().animate(animation_macro, animation_nbr)
        macro, side = animation_macro.split()
        if macro == "Walk":
            self.clock_speed = Config.CLOCK_SPEED
            self.speed = 1
            self.move(side)
        elif macro == "Run":
            self.clock_speed = Config.CLOCK_SPEED
            self.speed = 2
            self.move(side)
        elif macro == "Attack":
            self.clock_speed = 20
        # TODO: Implement Attack

    def save_location(self):
        self.old_position = self.position.copy()
        