import math

from character import Character
from constants import C_WALK_ANIMATION_COUNT
from saiyan import SuperSaiyanMixin


class NPC(Character):
    """A character that patrols a path and fights back when the player is near."""

    MAX_HP = 400
    # NPCs are tough: only this share of a hit gets through
    DAMAGE_TAKEN = 0.6
    ATTACK_DAMAGE = 2
    # Longer than the player's attack rhythm, so the NPC keeps fighting back
    FLINCH_COOLDOWN_MS = 1800
    # Distance (in pixels) under which the NPC considers a patrol point reached
    PATROL_ARRIVAL_DISTANCE = 2

    def __init__(self, pos_x, pos_y, is_transformed, name, nb_points, dialog_texts):
        super().__init__(pos_x, pos_y, name)
        self.name = name
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
        if is_transformed and self.can_transform:
            self._become_super()
            self.face_idle()

    def update_ai(self):
        """Decisions the NPC takes on its own during a fight."""

    def teleport_spawn(self):
        location = self.points[self.current_point]
        self.position[0] = location.x
        self.position[1] = location.y

    def load_points(self, game_map):
        """Read the patrol path ("<name>_path_<i>" objects) from the map."""
        self.points = [
            game_map.get_rect(game_map.get_object(f"{self.name}_path_{index}"))
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
    """A Saiyan NPC: goes Super Saiyan once the fight turns against him."""

    # Transforms when HP drops to this share of the maximum
    TRANSFORM_AT_HP = 0.5

    def update_ai(self):
        if (
            not self.is_super
            and 0 < self.hp <= self.max_hp * self.TRANSFORM_AT_HP
        ):
            self.transform()
