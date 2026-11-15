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
        self.max_hp = 100
        self.hp = self.max_hp
        self.max_ki = 100
        self.ki = self.max_ki
        self.facing = AnimationDirection.DOWN.value
        
    def update(self):
        self.rect.topleft = self.position
        self.feet.midbottom = self.rect.midbottom

    def move_back(self):
        self.position = self.old_position
        self.feet.midbottom = self.rect.midbottom
        #self.rect.topleft = self.rect.midbottom
    
    def move(self, animation_macro, animation_count, movement=None):
        macro, side = animation_macro.split()
        self.facing = side
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
        self.facing = side
        if not self.has_animation(f"{animation_macro} 0"):
            self.images = []
            self.current_animation_macro = None
            self.current_animation_index = 0
            self.clock = 0
            self.image = self.get_image_by_animation_name(f"IDLE {side}")
            if side == AnimationDirection.LEFT.value:
                self.image = pygame.transform.flip(self.image, True, False)
            self.animation_name = f"IDLE {side}"
            return

        if macro is not None and macro == AnimationType.ATTACK.value:
            self.clock_speed = 20
        self.animate(animation_macro, animation_count)

    def save_location(self):
        self.old_position = self.position.copy()

    def take_damage(self, amount):
        self.hp = max(0, self.hp - amount)
        