import math

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


    # Distance (in pixels) under which the NPC considers a patrol point reached
    PATROL_ARRIVAL_DISTANCE = 2

    def _target_index(self):
        return (self.current_point + 1) % len(self.points)

    def resume_patrol(self):
        """Head back to the closest patrol point (called when a fight is over).

        After a chase the NPC can be far away from its path. The patrol logic
        steers toward the next waypoint from the NPC's *actual* position, so it
        just needs to know which waypoint to go back to.
        """
        if not self.points:
            return
        nearest = min(
            range(len(self.points)),
            key=lambda index: math.hypot(
                self.points[index].x - self.position[0],
                self.points[index].y - self.position[1],
            ),
        )
        # current_point is the last point reached, the target is the next one
        self.current_point = (nearest - 1) % len(self.points)

    def _face_idle(self, direction):
        self.facing = direction
        self.image = self.get_image_by_animation_name(f"IDLE {direction}")
        if direction == "Left":
            self.image = pygame.transform.flip(self.image, True, False)

    def move_npc(self):
        """Walk the patrol path, independently of what the player is doing."""
        if self.is_defeated or self.combat_engaged or not self.points:
            return

        # Stand still while touching the player (so he can be talked to)
        if self.speed == 0:
            self._face_idle(self.facing)
            return

        target_rect = self.points[self._target_index()]
        # The patrol points are expressed in the same coordinates as the
        # sprite position (see teleport_spawn), so steer from the real position
        dx = target_rect.x - self.position[0]
        dy = target_rect.y - self.position[1]

        if math.hypot(dx, dy) <= self.PATROL_ARRIVAL_DISTANCE:
            self.current_point = self._target_index()
            return

        if abs(dx) >= abs(dy):
            direction = "Right" if dx > 0 else "Left"
        else:
            direction = "Down" if dy > 0 else "Up"
        self.move(f"Walk {direction}", C_WALK_ANIMATION_COUNT, (dx, dy))
