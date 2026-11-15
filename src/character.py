import pygame

from animation import Animation, AnimationDirection, AnimationType
from utils.config import Config
from constants import *

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
    
    def move(self, animation_macro, animation_count, movement=None):
        macro, side = animation_macro.split()
        if macro == AnimationType.WALK.value:
            self.clock_speed = Config.CLOCK_SPEED
            self.speed = 1
        elif macro == AnimationType.RUN.value:
            self.clock_speed = Config.CLOCK_SPEED
            self.speed = 2

        if movement is None:
            movement = {
                AnimationDirection.RIGHT.value: (1, 0),
                AnimationDirection.LEFT.value: (-1, 0),
                AnimationDirection.DOWN.value: (0, 1),
                AnimationDirection.UP.value: (0, -1),
            }[side]

        length = (movement[0] ** 2 + movement[1] ** 2) ** 0.5
        if length == 0:
            return

        self.old_position = self.position.copy()
        self.position[0] += movement[0] / length * self.speed
        self.position[1] += movement[1] / length * self.speed

        self.animate(animation_macro, animation_count)
        
    def attack(self, animation_macro, animation_count):
        macro, side = animation_macro.split()
        self.animate(animation_macro, animation_count)
        if macro is not None and macro == AnimationType.ATTACK.value:
            self.clock_speed = 20

    def save_location(self):
        self.old_position = self.position.copy()
        