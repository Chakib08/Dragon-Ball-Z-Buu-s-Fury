"""What the NPCs decide to do each frame: pick a foe, chase it (around
walls, see pathfinding.py), guard, punch, or now and then use a special
technique. Allies (team HEROES) fight the enemies and otherwise follow the
player; enemies fight the player and his allies.

The rules of a fight (damage, techniques, effects) are CombatSystem's: the
brain asks it to strike or to use a technique.
"""

import math
import random

import pygame

import pathfinding
from animation import AnimationDirection
from movement import resolve_movement_collisions, solid_bodies
from npc import HEROES
from utils import timing


def forward_lateral(direction, origin, target):
    """Offset of target from origin, split along and across the facing direction."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if direction == AnimationDirection.UP.value:
        return -dy, dx
    if direction == AnimationDirection.DOWN.value:
        return dy, dx
    if direction == AnimationDirection.LEFT.value:
        return -dx, dy
    return dx, dy


def direction_to(origin, target):
    """The facing (Right, Left, Down, Up) that looks most towards target."""
    dx = target[0] - origin[0]
    dy = target[1] - origin[1]
    if abs(dx) >= abs(dy):
        return AnimationDirection.RIGHT.value if dx >= 0 else AnimationDirection.LEFT.value
    return AnimationDirection.DOWN.value if dy >= 0 else AnimationDirection.UP.value


class NpcBrain:
    AGGRO_RANGE = 180
    # An ally walks back to the player when he is farther than this
    FOLLOW_DISTANCE = 40
    # Time an NPC leaves a target it found no path to
    UNREACHABLE_MS = 3000
    # Frames (at 60 FPS) without moving before an NPC looks for a path
    STUCK_FRAMES = 4
    # A path is dropped when its target moved this many cells away
    PATH_STALE_CELLS = 3
    # Techniques that fly straight need the target roughly in line
    AIM_TOLERANCE = 12

    def __init__(self, combat):
        self.combat = combat

    # ---- Who to fight ---------------------------------------------------------
    def foes_of(self, npc):
        """The fighters npc's side fights."""
        return self.combat.targets if npc.team == HEROES else self.combat.heroes

    def choose_target(self, npc, now):
        """The closest foe still standing within reach of the fight (for an
        ally: near itself or near the player), or None."""
        if now < npc.unreachable_until:
            return None
        near = [npc.feet.center]
        if npc.team == HEROES:
            near.append(self.combat.player.feet.center)  # protects the player too
        candidates = [
            foe for foe in self.foes_of(npc)
            if foe.hp > 0 and min(math.dist(point, foe.feet.center) for point in near) <= self.AGGRO_RANGE
        ]
        return min(candidates, key=lambda foe: math.dist(npc.feet.center, foe.feet.center), default=None)

    # ---- One frame ------------------------------------------------------------
    def update(self, npc, now, collisions):
        combat = self.combat
        if npc.hp <= 0:
            npc.is_defeated = True
            npc.combat_engaged = True
            npc.faint()
            return

        # Pushed back, flinching or transforming: no chasing or attacking.
        # An NPC flinches on every hit, but strikes back out of the flinch
        # as soon as its next strike is due (it cannot be stun-locked)
        pushed = npc.update_knockback(collisions, solid_bodies(combat.fighters, npc))
        busy = npc.update_action()
        if busy and npc.action["name"] == "hurt" and npc.target is None:
            npc.target = self.choose_target(npc, now)  # hit before it picked one
        if busy and npc.action["name"] == "hurt" and npc.target is not None and self.strike_due(npc, now):
            npc.cancel_hurt()
            busy = False
        if pushed or busy:
            return

        target = self.choose_target(npc, now)
        was_engaged = npc.combat_engaged
        npc.combat_engaged = target is not None
        npc.target = target
        if target is None:
            self._forget_path(npc)
            if npc.blocking:
                npc.stop_block()
            if npc.team == HEROES:
                self.follow_player(npc, collisions)
            elif was_engaged:
                # Everyone got away: go back to the patrol path
                npc.resume_patrol()
            return

        npc.update_ai()
        if npc.action is not None:
            return

        distance = math.dist(target.feet.center, npc.feet.center)
        # Up close, the NPC always turns to face its target
        if distance <= combat.reach(npc, target) + combat.ATTACK_LATERAL_TOLERANCE:
            npc.face_toward(target.feet.center)
        # Guard after a flurry of hits, then riposte
        if npc.wants_guard:
            npc.start_guard(now)
        if npc.update_guard(now):
            return

        if not was_engaged:
            npc.last_attack_ms = now
            self._forget_path(npc)
            npc.next_technique_ms = now + self.technique_delay(npc)

        # Now and then a special technique instead of a punch
        if self.try_technique(npc, target, now):
            return

        if self.in_attack_range(npc):
            npc.chase_stuck_frames = 0
            npc.chase_path = []
            # One punch or kick at a time, at the same pace as the player,
            # after a short reaction time
            if self.strike_due(npc, now):
                npc.last_attack_ms = now
                npc.strike()
                target.take_damage(npc.attack_damage * combat.damage_multiplier(npc), npc.feet.center)
            else:
                npc.face_idle()
        else:
            if npc.out_of_reach_since is None:
                npc.out_of_reach_since = now
            # A short trip out of reach (a hit's push) keeps the reaction
            if now - npc.out_of_reach_since > npc.REACH_GRACE_MS:
                npc.in_reach_since = None
            self.move_toward(npc, target.feet.center, collisions)

    def follow_player(self, npc, collisions):
        """An ally with nobody to fight stays close to the player."""
        player = self.combat.player
        if player.hp <= 0 or math.dist(npc.feet.center, player.feet.center) <= self.FOLLOW_DISTANCE:
            if npc.action is None:
                npc.face_idle()
            return
        npc.target = player  # for the path search's reach
        self.move_toward(npc, player.feet.center, collisions)
        npc.target = None

    # ---- Striking -------------------------------------------------------------
    def in_attack_range(self, npc):
        """Whether npc's punch reaches its target (the player if none)."""
        combat = self.combat
        foe = npc.target or combat.player
        forward, lateral = forward_lateral(npc.facing, npc.feet.center, foe.feet.center)
        tolerance = (foe.feet.width + npc.feet.width) / 2 + combat.ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= combat.reach(npc, foe) and abs(lateral) <= tolerance

    def strike_due(self, npc, now):
        """In reach of its target and either riposting after a guard, or past
        its reaction time and its cooldown."""
        if not self.in_attack_range(npc):
            return False
        npc.out_of_reach_since = None
        if npc.in_reach_since is None:
            npc.in_reach_since = now
        if npc.riposte_ready:
            npc.riposte_ready = False
            return True
        return (
            now - npc.in_reach_since >= npc.REACTION_MS
            and now - npc.last_attack_ms >= npc.attack_cooldown_ms
        )

    # ---- Special techniques ---------------------------------------------------
    def technique_delay(self, npc):
        """Some randomness, so the NPCs do not all fire at once."""
        return random.uniform(0.6, 1.4) * npc.technique_every_ms

    def technique_fits(self, npc, technique, target):
        """Whether the technique can reach the target from where npc stands."""
        dx = target.feet.centerx - npc.feet.centerx
        dy = target.feet.centery - npc.feet.centery
        distance = math.hypot(dx, dy)
        stats = technique.stats
        if technique.kind in ("projectile", "beam", "ball"):
            # They fly straight: the target must be roughly in line
            in_line = min(abs(dx), abs(dy)) <= self.AIM_TOLERANCE
            return in_line and self.combat.ATTACK_RANGE < distance <= stats["range"] * 0.9
        if technique.kind == "burst":
            return distance <= stats["radius"] * 0.8
        if technique.kind == "teleport":
            return 60 <= distance <= stats["reach"]
        return False

    def try_technique(self, npc, target, now):
        """When its next try is due, the NPC uses one of the techniques that
        fit (randomly chosen) if it has the ki. Returns True if it did."""
        if not npc.techniques or now < npc.next_technique_ms:
            return False
        options = [t for t in npc.techniques
                   if npc.ki >= t.cost and t.form_for(npc) is not None and self.technique_fits(npc, t, target)]
        if not options:
            return False  # tried again as soon as one fits
        npc.next_technique_ms = now + self.technique_delay(npc)
        return self.combat.use_technique(npc, random.choice(options), target)

    # ---- Moving ---------------------------------------------------------------
    @staticmethod
    def _forget_path(npc):
        npc.chase_path = []
        npc.chase_target = None
        npc.chase_stuck_frames = 0

    def move_toward(self, npc, target, collisions):
        """A step towards target (a point): straight at it, or along a path
        around the walls once walking straight got stuck."""
        if npc.chase_path and math.dist(
            pathfinding.cell_center(npc.chase_target), pathfinding.cell_center(pathfinding.grid_cell(target))
        ) > pathfinding.GRID_SIZE * self.PATH_STALE_CELLS:
            npc.chase_path = []
            npc.chase_target = None

        if npc.chase_path:
            if math.dist(npc.feet.center, pathfinding.cell_center(npc.chase_path[0])) <= pathfinding.GRID_SIZE:
                npc.chase_path.pop(0)
            if npc.chase_path:
                self.step_toward(npc, pathfinding.cell_center(npc.chase_path[0]), collisions)
                return

        starting_position = tuple(npc.position)
        self.step_toward(npc, target, collisions)
        if math.dist(starting_position, npc.position) < 0.01:
            npc.chase_stuck_frames += timing.ticks()
        else:
            npc.chase_stuck_frames = 0

        if npc.chase_stuck_frames >= self.STUCK_FRAMES:
            npc.chase_path = self.find_path(npc, target, collisions)
            npc.chase_target = pathfinding.grid_cell(target)
            npc.chase_stuck_frames = 0
            if npc.chase_path:
                self.step_toward(npc, pathfinding.cell_center(npc.chase_path[0]), collisions)
            elif hasattr(npc, "unreachable_until"):
                # No way there (across water, behind a wall): instead of
                # pushing against the obstacle forever, leave it for a while
                npc.unreachable_until = pygame.time.get_ticks() + self.UNREACHABLE_MS

    def find_path(self, npc, target, collisions):
        """The cells to walk to get within punching reach of target."""
        foe = npc.target or self.combat.player
        return pathfinding.find_path(npc, target, collisions, self.combat.reach(npc, foe))

    def step_toward(self, npc, target, collisions):
        dx = target[0] - npc.feet.centerx
        dy = target[1] - npc.feet.centery
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return
        npc.move(f"Walk {direction_to(npc.feet.center, target)}", 4, (dx, dy))
        npc.update()
        resolve_movement_collisions(npc, collisions, solid_bodies(self.combat.fighters, npc))
