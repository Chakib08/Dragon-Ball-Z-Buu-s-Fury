import math

import pygame

from animation import AnimationDirection
from character import Character
from constants import C_WALK_ANIMATION_COUNT
from saiyan import SuperSaiyanMixin


class NPC(Character):
    """A character that patrols a path and fights back when the player is near."""

    MAX_HP = 400
    # NPCs are tough: only this share of a hit gets through
    DAMAGE_TAKEN = 0.6
    ATTACK_DAMAGE = 2
    # After stepping into reach, the NPC waits this long before its first
    # strike: the player gets a chance to hit first
    REACTION_MS = 200
    # Pushed out of reach for less than this, the NPC keeps its reaction
    # (a hit's push must not make it wait again)
    REACH_GRACE_MS = 600
    # Hit this many times in quick succession (each within COMBO_WINDOW_MS
    # of the previous one), the NPC guards for GUARD_MS, then ripostes: it
    # strikes as soon as it can, without reaction time or cooldown
    GUARD_AFTER_HITS = 2
    COMBO_WINDOW_MS = 900
    GUARD_MS = 500
    # Distance (in pixels) under which the NPC considers a patrol point reached
    PATROL_ARRIVAL_DISTANCE = 2

    def __init__(self, pos_x, pos_y, is_transformed, name, nb_points, dialog_texts, path_name=None):
        super().__init__(pos_x, pos_y, name)
        self.name = name
        # Map objects "<path_name>_path_<i>" mark the patrol route
        self.path_name = path_name or name
        self.nb_points = nb_points
        self.points = []
        self.current_point = 0
        self.speed = 1
        self.dialog_texts = dialog_texts
        self.combat_engaged = False
        self.is_defeated = False
        self.chase_stuck_frames = 0
        self.chase_path = []
        self.chase_target = None
        self.attack_damage = self.ATTACK_DAMAGE
        self.attack_cooldown_ms = self.ATTACK_COOLDOWN_MS
        self.last_attack_ms = 0
        # When the player came within reach (None while out of reach), and
        # when the NPC last left it
        self.in_reach_since = None
        self.out_of_reach_since = None
        # Guard and riposte (see GUARD_AFTER_HITS)
        self.hits_in_a_row = 0
        self.last_hit_ms = None
        self.wants_guard = False
        self.guard_until_ms = None
        self.riposte_ready = False
        if is_transformed and self.can_transform:
            self._become_super()
            self.face_idle()

    def update_ai(self):
        """Decisions the NPC takes on its own during a fight."""

    def take_damage(self, amount, source=None):
        if not self.blocking:
            now = pygame.time.get_ticks()
            in_a_row = self.last_hit_ms is not None and now - self.last_hit_ms <= self.COMBO_WINDOW_MS
            self.hits_in_a_row = self.hits_in_a_row + 1 if in_a_row else 1
            self.last_hit_ms = now
            if self.hits_in_a_row >= self.GUARD_AFTER_HITS:
                # Guards once this hit's hurt animation is over
                self.wants_guard = True
                self.hits_in_a_row = 0
        return super().take_damage(amount, source)

    def start_guard(self, now):
        if self.start_block():
            self.wants_guard = False
            self.guard_until_ms = now + self.GUARD_MS
            self.riposte_ready = True

    def update_guard(self, now):
        """Keep guarding until its time is up. Returns True while guarding."""
        if not self.blocking:
            return False
        if now < self.guard_until_ms:
            return True
        self.stop_block()
        self.guard_until_ms = None
        return False

    def face_toward(self, point):
        dx = point[0] - self.feet.centerx
        dy = point[1] - self.feet.centery
        if abs(dx) >= abs(dy):
            direction = AnimationDirection.RIGHT.value if dx >= 0 else AnimationDirection.LEFT.value
        else:
            direction = AnimationDirection.DOWN.value if dy >= 0 else AnimationDirection.UP.value
        if direction != self.facing:
            self.facing = direction
            if self.blocking:
                self.start_block()  # guard pose in the new direction
            elif self.action is None:
                self.face_idle()

    def teleport_spawn(self):
        location = self.points[self.current_point]
        self.position[0] = location.x
        self.position[1] = location.y

    def load_points(self, game_map):
        """Read the patrol path ("<path_name>_path_<i>" objects) from the map."""
        self.points = [
            game_map.get_rect(game_map.get_object(f"{self.path_name}_path_{index}"))
            for index in range(self.nb_points)
        ]
        self.save_location()

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

    def move_npc(self):
        """Walk the patrol path, independently of what the player is doing."""
        if self.is_defeated or self.combat_engaged or not self.points:
            return

        # Stand still while touching the player (so he can be talked to)
        if self.speed == 0:
            self.face_idle()
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


class SaiyanNPC(SuperSaiyanMixin, NPC):
    """A Saiyan NPC: powers up once the fight turns against him.

    With a base and a Super Saiyan sheet he transforms; with only a Super
    Saiyan sheet he already looks the part and just gains the power.
    """

    # Powers up when HP drops to this share of the maximum
    TRANSFORM_AT_HP = 0.5

    def update_ai(self):
        if self.powered_up or not 0 < self.hp <= self.max_hp * self.TRANSFORM_AT_HP:
            return
        if self.has_form(self.BASE_FORM) and self.has_form(self.SUPER_FORM):
            self.transform()
        else:
            self.power_up()
