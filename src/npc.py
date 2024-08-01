import pygame

from character import Character
from constants import *

class NPC(Character):
    def __init__(self, pos_x, pos_y, isTransformed, name, nb_points, dialog_texts):
        super().__init__(pos_x, pos_y, name)
        self.isTransofrmed = isTransformed
        self.rect = self.image.get_rect()
        self.name = name
        self.nb_points = nb_points
        self.points = []
        self.current_point = 0
        self.speed = 1
        self.dialog_texts = dialog_texts

    def teleport_spawn(self):
        location = self.points[self.current_point]
        self.position[0] = location.x
        self.position[1] = location.y

    def load_points(self, map):
        for i in range(self.nb_points):
            point = map.get_object(f"{self.name}_path_{i}")
            rect = map.get_rect(point)
            self.points.append(rect)
            self.save_location()


    def move_npc(self):
        current_point = self.current_point
        target_point = current_point + 1

        # Ensure target_point is within the bounds of the points list
        if target_point >= len(self.points):
            target_point = 0  # Reset to the first point or handle appropriately

        current_rect = self.points[current_point]
        target_rect = self.points[target_point]

        if current_rect.y < target_rect.y and abs(current_rect.x - target_rect.x) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_DOWN)
            else:
                self.move(C_WALK_DOWN, C_WALK_ANIMATION_COUNT)
        elif current_rect.y > target_rect.y and abs(current_rect.x - target_rect.x) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_UP)
            else:
                self.move(C_WALK_UP, C_WALK_ANIMATION_COUNT)
        elif current_rect.x > target_rect.x and abs(current_rect.y - target_rect.y) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_LEFT)
                self.image = pygame.transform.flip(self.image, True, False)
            else:
                self.move(C_WALK_LEFT, C_WALK_ANIMATION_COUNT)
        elif current_rect.x < target_rect.x and abs(current_rect.y - target_rect.y) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_RIGHT)
            else:
                self.move(C_WALK_RIGHT, C_WALK_ANIMATION_COUNT)

        if self.rect.colliderect(target_rect):
            self.current_point = target_point