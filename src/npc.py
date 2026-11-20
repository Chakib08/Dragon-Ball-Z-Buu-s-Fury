import math

import pygame

from animation import AnimationDirection
from character import Character
from constants import C_WALK_ANIMATION_COUNT
from difficulty import ALLY_DIFFICULTY, Difficulty, difficulty as find_difficulty, enemy_profile
from saiyan import SuperSaiyanMixin
from stats import power_ups


# The two sides of a fight: the player and his support characters, and the
# enemies
HEROES = "heroes"
ENEMIES = "enemies"


class NPC(Character):
    """A character the game controls. An enemy patrols a path and fights the
    player (and his allies) when they come near; an ally (team HEROES)
    follows the player and fights the enemies."""

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

    def __init__(self, pos_x, pos_y, is_transformed, name, nb_points, dialog_texts, path_name=None,
                 difficulty=None, team=ENEMIES):
        """difficulty: a Difficulty or its name; by default the one
        Config/enemies.json gives this character (an ally: "ally")."""
        super().__init__(pos_x, pos_y, name)
        self.team = team
        # Who it fights right now (chosen by the combat each frame)
        self.target = None
        # The target could not be reached (no path): leave it until then
        self.unreachable_until = 0
        # When it next considers a special technique (see CombatSystem)
        self.next_technique_ms = 0
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
        # The brain's notes (npc_ai.py): which incoming effects it decided
        # to dodge, when it next considers blocking, since when it lines up
        # a technique
        self.dodge_rolls = {}
        self.next_block_roll_ms = 0
        self.lineup_since = None
        if difficulty is None:
            difficulty = find_difficulty(ALLY_DIFFICULTY) if team == HEROES else enemy_profile(name).difficulty
        elif not isinstance(difficulty, Difficulty):
            difficulty = find_difficulty(difficulty)
        self.apply_difficulty(difficulty)
        if is_transformed and self.can_transform:
            self._become_super()
            self.face_idle()

    def apply_difficulty(self, difficulty):
        """Scale this enemy's strength (see difficulty.py); speed is already
        the character's own (Character), the power applies to every hit
        (CombatSystem)."""
        self.difficulty = difficulty
        # On top of the character's own stats (see stats.py)
        stats = self.stats
        self.max_hp = round(self.MAX_HP * stats.hp * difficulty.hp)
        self.hp = self.max_hp
        self.attack_damage = self.ATTACK_DAMAGE * difficulty.damage
        self.damage_taken = self.DAMAGE_TAKEN * difficulty.damage_taken / stats.defense
        self.reaction_ms = difficulty.reaction_ms
        self.attack_cooldown_ms = self.ATTACK_COOLDOWN_MS * difficulty.attack_cooldown
        self.guard_after_hits = difficulty.guard_after_hits
        self.guard_ms = self.GUARD_MS if difficulty.guard_ms is None else difficulty.guard_ms
        self.walk_speed = self.WALK_SPEED * stats.speed * difficulty.speed
        self.run_speed = self.RUN_SPEED * stats.speed * difficulty.speed
        # Share of HP left at which a Saiyan powers up (see SaiyanNPC)
        self.transform_at_hp = difficulty.power_up_at
        self.technique_every_ms = difficulty.technique_every_ms
        self.technique_damage = difficulty.technique_damage
        # How smart it fights (see npc_ai.py)
        self.dodge_chance = difficulty.dodge
        self.block_chance = difficulty.block_chance
        self.tactics = difficulty.tactics

    def update_ai(self):
        """Decisions the NPC takes on its own during a fight."""

    def take_damage(self, amount, source=None, push=1.0):
        if not self.blocking:
            now = pygame.time.get_ticks()
            in_a_row = self.last_hit_ms is not None and now - self.last_hit_ms <= self.COMBO_WINDOW_MS
            self.hits_in_a_row = self.hits_in_a_row + 1 if in_a_row else 1
            self.last_hit_ms = now
            if self.hits_in_a_row >= self.guard_after_hits:
                # Guards once this hit's hurt animation is over
                self.wants_guard = True
                self.hits_in_a_row = 0
        return super().take_damage(amount, source, push)

    def start_guard(self, now):
        if self.start_block():
            self.wants_guard = False
            self.guard_until_ms = now + self.guard_ms
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

    # The map's spawn and patrol points are the top-left corner of a sprite
    # of this size (most sheets); bigger or smaller sprites are placed so
    # their feet stand on the same spot (Broly's would else be 32 px lower,
    # on the other side of a cliff)
    MAP_SPRITE_SIZE = 32

    def position_at(self, point):
        """The position (top-left) that puts the feet where point says."""
        return (
            point.x + (self.MAP_SPRITE_SIZE - self.rect.width) / 2,
            point.y + self.MAP_SPRITE_SIZE - self.rect.height,
        )

    def teleport_spawn(self):
        if not self.points:
            return  # placed by whoever created it (an ally)
        self.position = list(self.position_at(self.points[self.current_point]))
        self.update()
        self.save_location()

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
                self.position_at(self.points[index])[0] - self.position[0],
                self.position_at(self.points[index])[1] - self.position[1],
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

        # Steer from the real position to where the next point puts the
        # sprite (see position_at)
        target_x, target_y = self.position_at(self.points[self._target_index()])
        dx = target_x - self.position[0]
        dy = target_y - self.position[1]

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

    def update_ai(self):
        steps = power_ups(self.character_name)
        if steps:
            self._power_up_by_steps(steps)
            return
        # Powers up when HP drops to transform_at_hp of the maximum
        if self.powered_up or not 0 < self.hp <= self.max_hp * self.transform_at_hp:
            return
        if self.has_form(self.BASE_FORM) and self.has_form(self.SUPER_FORM):
            self.transform()
        else:
            self.power_up()

    def _power_up_by_steps(self, steps):
        """Transform into the strongest level whose HP share is reached
        (Config/stats.json "power_ups"), never back to a weaker one. It
        waits for the ki a level needs (see SuperSaiyanMixin)."""
        if self.hp <= 0 or self.action is not None:
            return
        share = self.hp / self.max_hp
        order = [form for form, _ in steps]
        reached = [form for form, at in steps if share <= at and self.has_form(form)]
        if not reached:
            return
        wanted = reached[-1]
        if self.form in order and order.index(self.form) >= order.index(wanted):
            return  # already there (or stronger)
        levels = self.super_levels
        if wanted not in levels:
            return
        self.selected_level = levels.index(wanted)
        self.stop_block()
        self.transform()
