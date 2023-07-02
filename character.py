import pygame
from animation import Animation

class Character(Animation):
    def __init__(self, pos_x, pos_y, json_file):
        super().__init__(json_file)
        
        # self.hp = hp
        # self.ki = ki
        self.speed = 4
        self.position = [pos_x, pos_y]
        
    def update(self):
        self.rect.topleft = self.position
    
    def walk(self, side, speed):
        self.side = side
        
        if(self.side == "right"):
            self.position[0] += self.speed

        if(self.side == "left"):
            self.position[0] -= self.speed

        if(self.side == "down"):
            self.position[1] += self.speed

        if(self.side == "up"):
            self.position[1] -= self.speed
            
    def run():
        pass
    
    def attack():
        pass
    
            
    def animate(self, animation_macro, animation_nbr, capability):
        super().animate(animation_macro, animation_nbr)
        if capability == "Walk":
            self.walk("up", self.speed)
        elif capability == "Run":
            pass
        elif capability == "Attack":
            pass
        else:
            pass
            
    

    
