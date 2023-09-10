from animation import Animation
import pygame

class Character(Animation):
    def __init__(self, pos_x, pos_y, json_file):
        super().__init__(json_file)
        
        # self.hp = hp
        # self.ki = ki
        self.speed = 4
        self.position = [pos_x, pos_y]
        self.rect = self.image.get_rect()
        self.feet = pygame.Rect(0, 0, self.rect.width * 0.5, 12)
        self.old_position = self.position.copy()

        
    def update(self):
        self.rect.topleft = self.position
        self.feet.midbottom = self.rect.midbottom
        
    def move_back(self):
        self.position = self.old_position
        self.feet.midbottom = self.rect.midbottom
        self.rect.topleft = self.rect.midbottom
    
    def move(self, side, speed):
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

    def save_location(self):
        self.old_position = self.position.copy()
        