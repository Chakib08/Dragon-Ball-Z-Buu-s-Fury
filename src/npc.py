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
        self.max_hp = 60
        self.hp = self.max_hp
        self.combat_engaged = False
        self.is_defeated = False
        self.chase_stuck_frames = 0
        self.chase_path = []
        self.chase_target = None
        self.attack_damage = 8
        self.attack_cooldown_ms = 1000
        self.last_attack_ms = 0

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
        if self.is_defeated or self.combat_engaged or not self.points:
            return

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
                self.facing = "Down"
            else:
                self.move(C_WALK_DOWN, C_WALK_ANIMATION_COUNT)
        elif current_rect.y > target_rect.y and abs(current_rect.x - target_rect.x) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_UP)
                self.facing = "Up"
            else:
                self.move(C_WALK_UP, C_WALK_ANIMATION_COUNT)
        elif current_rect.x > target_rect.x and abs(current_rect.y - target_rect.y) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_LEFT)
                self.image = pygame.transform.flip(self.image, True, False)
                self.facing = "Left"
            else:
                self.move(C_WALK_LEFT, C_WALK_ANIMATION_COUNT)
        elif current_rect.x < target_rect.x and abs(current_rect.y - target_rect.y) < 20:
            if self.speed == 0:
                self.image = self.get_image_by_animation_name(C_IDLE_RIGHT)
                self.facing = "Right"
            else:
                self.move(C_WALK_RIGHT, C_WALK_ANIMATION_COUNT)

        if self.rect.colliderect(target_rect):
            self.current_point = target_point