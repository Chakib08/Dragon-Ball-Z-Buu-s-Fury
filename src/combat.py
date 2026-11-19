import math
import heapq
import random

import pygame

from animation import AnimationDirection
from character import DIRECTION_VECTORS
from effects import ChargeGlow, build_effect, effect_origin
from movement import resolve_movement_collisions, solid_bodies
from npc import HEROES


class CombatSystem:
    AGGRO_RANGE = 180
    # Melee reach in map pixels between the two characters' feet, the same
    # for the player and the NPCs: bodies (15-25 px wide) nearly touch
    ATTACK_RANGE = 22
    ATTACK_LATERAL_TOLERANCE = 8
    NPC_ATTACK_RANGE = ATTACK_RANGE
    NPC_ATTACK_LATERAL_TOLERANCE = ATTACK_LATERAL_TOLERANCE
    # Sprites up to this wide count as ordinary bodies; a bigger one (Broly)
    # adds this share of the extra width to the reach, for hitting him and
    # for his own hits, so fighters touching him can hit and be hit
    STANDARD_BODY_WIDTH = 32
    BIG_BODY_REACH = 0.4
    PATH_GRID_SIZE = 8
    # One punch or kick per button press, at most one every
    # Character.ATTACK_COOLDOWN_MS (the pace NPCs strike at too)
    PLAYER_ATTACK_DAMAGE = 15
    KI_REGEN_PER_SECOND = 12
    # Super Saiyan: hits harder, but burns ki instead of regenerating it
    # Super Saiyan punches, kicks and techniques do twice the damage (SSJ3
    # even more); a powered-up NPC gets a smaller boost, so story fights
    # stay winnable
    SUPER_DAMAGE_MULTIPLIER = 2.0
    SUPER_3_DAMAGE_MULTIPLIER = 2.5
    NPC_SUPER_DAMAGE_MULTIPLIER = 1.5
    # Ki drained per second by each Super Saiyan level: very slow (a full
    # bar keeps SSJ going for about 100 s), a little more for SSJ3
    SUPER_KI_DRAIN_PER_SECOND = {"ssj": 1, "ssj3": 2}

    def __init__(self, player, screen_size):
        self.player = player
        self.screen_size = screen_size
        self.last_update_ms = pygame.time.get_ticks()
        self.last_player_attack_ms = self.last_update_ms - player.ATTACK_COOLDOWN_MS
        # True when the last update() started a player attack
        self.player_swung = False
        # Special techniques: the selected one, when each was last used, the
        # effects on screen (and those added this frame, for the map to draw)
        self.selected_technique = 0
        self.last_technique_ms = {}
        self.effects = []
        self.new_effects = []
        # Called with (technique id, direction, origin) when the player
        # releases one (online play shows it to the opponent)
        self.on_technique = None
        # A technique being charged (button held), see start_special
        self.charge = None
        # Who can be hit and the walls, as of the last update
        self._targets = []
        self._collisions = []
        self._fighters = [player]
        self._heroes = [player]
        self.font = pygame.font.Font(None, 30)
        self.name_font = pygame.font.Font(None, 22)
        # Text is rendered once and reused every frame
        self._labels = {}

    def update(self, npcs, collisions, player_attacking=False, opponents=()):
        """One frame of combat. npcs are fought by the AI below: enemies
        fight the player and his allies, allies (team HEROES) fight the
        enemies. opponents (online players) are only targets for the
        player's hits."""
        now = pygame.time.get_ticks()
        elapsed_seconds = max(0, now - self.last_update_ms) / 1000
        self.last_update_ms = now
        if self.player.can_revert:
            self.player.ki = max(
                0, self.player.ki - self.SUPER_KI_DRAIN_PER_SECOND.get(self.player.form, 1) * elapsed_seconds
            )
            if self.player.ki <= 0:
                self.player.revert()
        else:
            self.player.ki = min(
                self.player.max_ki,
                self.player.ki + self.KI_REGEN_PER_SECOND * elapsed_seconds,
            )
        enemies = [npc for npc in npcs if npc.team != HEROES]
        allies = [npc for npc in npcs if npc.team == HEROES]
        # What the player, and his allies' and his techniques, can hit
        targets = [*enemies, *opponents]
        self._targets, self._collisions = targets, collisions
        self._heroes = [self.player, *allies]
        # Everyone on the field: their bodies block each other
        self._fighters = [self.player, *npcs, *opponents]
        for npc in npcs:
            npc.ki = min(npc.max_ki, npc.ki + self.NPC_KI_REGEN_PER_SECOND * elapsed_seconds)
        self._update_charge()
        self._update_effects()

        self.player_swung = False
        self.player.update_knockback(collisions, solid_bodies(self._fighters, self.player))
        if self.player.hp <= 0:
            self.player.faint()
        elif player_attacking:
            self._player_attack(targets, now)

        for npc in tuple(npcs):
            self._update_npc(npc, now, collisions)

    # An ally walks back to the player when he is farther than this
    FOLLOW_DISTANCE = 40
    NPC_KI_REGEN_PER_SECOND = 6
    # Time an NPC leaves a target it found no path to
    UNREACHABLE_MS = 3000

    def foes_of(self, npc):
        """The fighters npc's side fights."""
        return self._targets if npc.team == HEROES else self._heroes

    def _choose_target(self, npc, now):
        """The closest foe still standing within reach of the fight (for an
        ally: near itself or near the player), or None."""
        if now < npc.unreachable_until:
            return None
        near = [npc.feet.center]
        if npc.team == HEROES:
            near.append(self.player.feet.center)  # protects the player too
        candidates = [
            foe for foe in self.foes_of(npc)
            if foe.hp > 0 and min(self._distance(point, foe.feet.center) for point in near) <= self.AGGRO_RANGE
        ]
        return min(candidates, key=lambda foe: self._distance(npc.feet.center, foe.feet.center), default=None)

    def _update_npc(self, npc, now, collisions):
        if npc.hp <= 0:
            npc.is_defeated = True
            npc.combat_engaged = True
            npc.faint()
            return

        # Pushed back, flinching or transforming: no chasing or attacking.
        # An NPC flinches on every hit, but strikes back out of the flinch
        # as soon as its next strike is due (it cannot be stun-locked)
        pushed = npc.update_knockback(collisions, solid_bodies(self._fighters, npc))
        busy = npc.update_action()
        if busy and npc.action["name"] == "hurt" and npc.target is None:
            npc.target = self._choose_target(npc, now)  # hit before it picked one
        if busy and npc.action["name"] == "hurt" and npc.target is not None and self._npc_strike_due(npc, now):
            npc.cancel_hurt()
            busy = False
        if pushed or busy:
            return

        target = self._choose_target(npc, now)
        was_engaged = npc.combat_engaged
        npc.combat_engaged = target is not None
        npc.target = target
        if target is None:
            npc.chase_path = []
            npc.chase_target = None
            npc.chase_stuck_frames = 0
            if npc.blocking:
                npc.stop_block()
            if npc.team == HEROES:
                self._follow_player(npc, collisions)
            elif was_engaged:
                # Everyone got away: go back to the patrol path
                npc.resume_patrol()
            return

        npc.update_ai()
        if npc.action is not None:
            return

        distance = self._distance(target.feet.center, npc.feet.center)
        # Up close, the NPC always turns to face its target
        if distance <= self._reach(npc, target, self.ATTACK_RANGE) + self.ATTACK_LATERAL_TOLERANCE:
            npc.face_toward(target.feet.center)
        # Guard after a flurry of hits, then riposte
        if npc.wants_guard:
            npc.start_guard(now)
        if npc.update_guard(now):
            return

        if not was_engaged:
            npc.last_attack_ms = now
            npc.chase_stuck_frames = 0
            npc.chase_path = []
            npc.chase_target = None
            npc.next_technique_ms = now + self._technique_delay(npc)

        # Now and then a special technique instead of a punch
        if self._try_npc_technique(npc, target, now):
            return

        if self._npc_in_attack_range(npc):
            npc.chase_stuck_frames = 0
            npc.chase_path = []
            # One punch or kick at a time, at the same pace as the player,
            # after a short reaction time
            if self._npc_strike_due(npc, now):
                npc.last_attack_ms = now
                npc.strike()
                target.take_damage(npc.attack_damage * self._damage_multiplier(npc), npc.feet.center)
            else:
                npc.face_idle()
        else:
            if npc.out_of_reach_since is None:
                npc.out_of_reach_since = now
            # A short trip out of reach (a hit's push) keeps the reaction
            if now - npc.out_of_reach_since > npc.REACH_GRACE_MS:
                npc.in_reach_since = None
            self._move_toward(npc, target.feet.center, collisions)

    def _follow_player(self, npc, collisions):
        """An ally with nobody to fight stays close to the player."""
        if self.player.hp <= 0 or \
                self._distance(npc.feet.center, self.player.feet.center) <= self.FOLLOW_DISTANCE:
            if npc.action is None:
                npc.face_idle()
            return
        npc.target = self.player  # for the path search's reach
        self._move_toward(npc, self.player.feet.center, collisions)
        npc.target = None

    # ---- NPC special techniques -------------------------------------------------
    def _technique_delay(self, npc):
        """Some randomness, so the NPCs do not all fire at once."""
        return random.uniform(0.6, 1.4) * npc.technique_every_ms

    def _technique_fits(self, npc, technique, target):
        """Whether the technique can reach the target from where npc stands."""
        dx = target.feet.centerx - npc.feet.centerx
        dy = target.feet.centery - npc.feet.centery
        distance = math.hypot(dx, dy)
        stats = technique.stats
        if technique.kind in ("projectile", "beam", "ball"):
            # They fly straight: the target must be roughly in line
            in_line = min(abs(dx), abs(dy)) <= self.NPC_AIM_TOLERANCE
            return in_line and self.ATTACK_RANGE < distance <= stats["range"] * 0.9
        if technique.kind == "burst":
            return distance <= stats["radius"] * 0.8
        if technique.kind == "teleport":
            return 60 <= distance <= stats["reach"]
        return False

    NPC_AIM_TOLERANCE = 12

    def _try_npc_technique(self, npc, target, now):
        """When its next try is due, the NPC uses one of the techniques that
        fit (randomly chosen) if it has the ki. Returns True if it did."""
        if not npc.techniques or now < npc.next_technique_ms:
            return False
        options = [t for t in npc.techniques
                   if npc.ki >= t.cost and t.form_for(npc) is not None and self._technique_fits(npc, t, target)]
        if not options:
            return False  # tried again as soon as one fits
        npc.next_technique_ms = now + self._technique_delay(npc)
        return self.use_technique(npc, random.choice(options), target)

    def use_technique(self, user, technique, target=None):
        """An NPC (or any character but the player, who uses start_special)
        uses a technique towards target: its pose, then the effect. Charged
        techniques go off at three quarters of their power."""
        if user.hp <= 0 or user.action is not None:
            return False
        direction = user.facing
        if target is not None:
            dx = target.feet.centerx - user.feet.centerx
            dy = target.feet.centery - user.feet.centery
            if abs(dx) >= abs(dy):
                direction = AnimationDirection.RIGHT.value if dx >= 0 else AnimationDirection.LEFT.value
            else:
                direction = AnimationDirection.DOWN.value if dy >= 0 else AnimationDirection.UP.value
        user.facing = direction
        sprites = technique.form_for(user)
        frames = user.get_frames(technique.pose_macro(direction))
        if sprites is None or not frames:
            return False
        if technique.kind == "teleport":
            user._play("teleport", frames, user.SPECIAL_CLOCK_SPEED,
                       on_done=lambda: self._teleport(technique, user, target))
        else:
            power = 0.75 if technique.kind in self.CHARGEABLE else None
            user._play(
                "special", frames, user.SPECIAL_CLOCK_SPEED,
                hold_ticks=40 if technique.kind == "beam" else 8,
                on_frame=(min(sprites.fire_frame(direction), len(frames) - 1),
                          lambda: self._release_by(user, technique, direction, power)),
            )
        user.ki -= technique.cost
        return True

    def _npc_strike_due(self, npc, now):
        """In reach of the player and either riposting after a guard, or past
        its reaction time and its cooldown."""
        if not self._npc_in_attack_range(npc):
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

    def _player_attack(self, npcs, now):
        """Strike once, if the player is free to: plays one punch or kick
        and hits the closest enemy in front, if there is one."""
        player = self.player
        if (
            now - self.last_player_attack_ms < player.ATTACK_COOLDOWN_MS
            or player.action is not None
        ):
            return

        self.last_player_attack_ms = now
        self.player_swung = True
        player.strike()

        targets = [npc for npc in npcs if npc.hp > 0 and self._is_in_attack_range(npc)]
        if not targets:
            return
        target = min(targets, key=lambda npc: self._distance(player.rect.center, npc.rect.center))
        target.take_damage(
            self.PLAYER_ATTACK_DAMAGE * self._damage_multiplier(player), player.feet.center
        )

    def _damage_multiplier(self, attacker):
        if not attacker.powered_up:
            return 1
        if attacker is self.player:
            if attacker.form == attacker.SUPER_3_FORM:
                return self.SUPER_3_DAMAGE_MULTIPLIER
            return self.SUPER_DAMAGE_MULTIPLIER
        return self.NPC_SUPER_DAMAGE_MULTIPLIER

    # ---- Special techniques (ki) ---------------------------------------------
    @property
    def techniques(self):
        return self.player.techniques

    @property
    def technique(self):
        """The technique the ki button uses."""
        techniques = self.techniques
        if not techniques:
            return None
        return techniques[self.selected_technique % len(techniques)]

    def cycle_technique(self, step):
        if self.techniques:
            self.selected_technique = (self.selected_technique + step) % len(self.techniques)

    def start_special(self):
        """Use the selected technique: the character's pose, then its effect.

        Returns True if it started (enough ki, not busy, off cooldown).
        """
        player = self.player
        technique = self.technique
        now = pygame.time.get_ticks()
        if technique is None or player.hp <= 0 or player.action is not None:
            return False
        if player.ki < technique.cost:
            return False
        last = self.last_technique_ms.get(technique.id)
        if last is not None and now - last < technique.stats["cooldown_ms"]:
            return False
        sprites = technique.form_for(player)
        facing = player.facing
        frames = player.get_frames(technique.pose_macro(facing))
        if sprites is None or not frames:
            return False

        if technique.kind in self.CHARGEABLE:
            self._start_charge(technique, sprites, facing, frames, now)
        elif technique.kind == "teleport":
            player._play("teleport", frames, player.SPECIAL_CLOCK_SPEED,
                         on_done=lambda: self._teleport(technique))
        else:
            hold = 40 if technique.kind == "beam" else 8
            player._play(
                "special", frames, player.SPECIAL_CLOCK_SPEED, hold_ticks=hold,
                on_frame=(min(sprites.fire_frame(facing), len(frames) - 1),
                          lambda: self._release(technique, facing)),
            )
        player.ki -= technique.cost
        self.last_technique_ms[technique.id] = now
        return True

    # ---- Charging (beams and ki balls) ------------------------------------------
    CHARGEABLE = ("beam", "ball")
    # Time to charge fully; the technique is released by itself then
    CHARGE_MS = 1500

    @property
    def charging(self):
        return self.charge is not None

    @property
    def charge_level(self):
        """0 when the charge starts, 1 when full."""
        if self.charge is None:
            return 0.0
        elapsed = pygame.time.get_ticks() - self.charge["start_ms"]
        return max(0.0, min(1.0, elapsed / self.CHARGE_MS))

    def _start_charge(self, technique, sprites, facing, frames, now):
        """The charging pose (frames before the firing one) is held while the
        button is held; the firing frames play on release."""
        player = self.player
        fire_at = max(0, min(sprites.fire_frame(facing), len(frames) - 1))
        charge_frames = frames[:fire_at] or frames[:1]
        fire_frames = frames[fire_at:] or frames[-1:]
        player._play("charging", charge_frames, player.SPECIAL_CLOCK_SPEED, hold_ticks=10 ** 9)
        glow_frames = sprites.cuts("charge") or sprites.cuts("grow")
        glow = ChargeGlow(glow_frames, player) if glow_frames else None
        if glow is not None:
            self.add_effect(glow)
        self.charge = {"technique": technique, "direction": facing, "start_ms": now,
                       "fire_frames": fire_frames, "glow": glow}

    def release_charge(self):
        """Let the charged technique go, as strong as it got."""
        charge, self.charge = self.charge, None
        if charge is None:
            return
        power = self.charge_level_of(charge)
        if charge["glow"] is not None:
            charge["glow"].done = True
        technique, direction = charge["technique"], charge["direction"]
        player = self.player
        player._play(
            "special", charge["fire_frames"], player.SPECIAL_CLOCK_SPEED,
            hold_ticks=40 if technique.kind == "beam" else 8,
            on_frame=(0, lambda: self._release(technique, direction, power)),
        )

    @staticmethod
    def charge_level_of(charge):
        elapsed = pygame.time.get_ticks() - charge["start_ms"]
        return max(0.0, min(1.0, elapsed / CombatSystem.CHARGE_MS))

    def _update_charge(self):
        charge = self.charge
        if charge is None:
            return
        action = self.player.action
        if action is None or action["name"] != "charging":
            # Hit (or knocked out) while charging: the charge is lost
            self.charge = None
            if charge["glow"] is not None:
                charge["glow"].done = True
            return
        level = self.charge_level_of(charge)
        if charge["glow"] is not None:
            charge["glow"].level = level
        if level >= 1:
            self.release_charge()  # fully charged: it goes by itself

    def draw_charge(self, screen, to_screen_rect):
        """A small bar above the player while a technique charges."""
        if self.charge is None:
            return
        on_screen = pygame.Rect(to_screen_rect(self.player.rect))
        width = max(48, on_screen.width)
        bar = pygame.Rect(0, 0, width, 8)
        bar.midbottom = (on_screen.centerx, on_screen.top - 6)
        level = self.charge_level
        pygame.draw.rect(screen, (35, 35, 42), bar)
        color = (255, 230, 120) if level >= 1 else (120, 210, 255)
        pygame.draw.rect(screen, color, (bar.x, bar.y, round(bar.width * level), bar.height))
        pygame.draw.rect(screen, self.FRAME_COLOR, bar, 1)

    def _hit_target(self, target, damage, source, push):
        target.take_damage(damage, source, push)

    def _release(self, technique, direction, power=None):
        """The player's pose reached its firing frame (see _release_by)."""
        effect = self._release_by(self.player, technique, direction, power)
        if effect is not None and self.on_technique is not None:
            self.on_technique(technique.id, direction, effect_origin(effect, self.player, direction), power)

    def _release_by(self, user, technique, direction, power=None):
        """The pose reached its firing frame: the effect leaves user's hands,
        towards the other side. power: how charged it was (0 to 1); a tap
        does half the damage. An NPC's technique does a share of it (see
        difficulty.py)."""
        if user.hp <= 0:
            return None
        damage = technique.damage * self._damage_multiplier(user)
        if user is not self.player:
            damage *= getattr(user, "technique_damage", 1.0)
        if power is not None:
            damage *= 0.5 + 0.5 * power
        effect = build_effect(technique, technique.form_for(user), user, direction,
                              damage, self._hit_target, self.add_effect, power=power)
        if effect is not None:
            effect.team = user.team
            self.add_effect(effect)
        return effect

    def show_opponent_technique(self, opponent, technique_id, direction, origin, power=None):
        """Draw a technique the online opponent used. It stops on the player
        but does no damage here: the opponent's game sends the hit."""
        technique = next((t for t in opponent.techniques if t.id == technique_id), None)
        if technique is None or technique.kind == "teleport" or direction not in DIRECTION_VECTORS:
            return
        effect = build_effect(technique, technique.form_for(opponent), opponent, direction,
                              0, None, self.add_effect, origin=origin, power=power)
        if effect is not None:
            effect.hits_player = True
            self.add_effect(effect)

    def add_effect(self, effect):
        self.effects.append(effect)
        self.new_effects.append(effect)

    def clear_effects(self):
        """End every effect at once (the player went to another map: a blast
        left behind must not fly on there, nor stay drawn on the old map)."""
        for effect in self.effects:
            effect.done = True
        self.effects.clear()
        self.new_effects.clear()

    def _update_effects(self):
        for effect in tuple(self.effects):
            if getattr(effect, "hits_player", False):
                victims = [self.player]  # drawn for the online opponent
            elif getattr(effect, "team", HEROES) == HEROES:
                victims = self._targets
            else:
                victims = self._heroes
            effect.update_effect(victims)
            if effect.done:
                self.effects.remove(effect)

    @staticmethod
    def _place_feet(character, feet):
        """Move character so its feet are centred on feet."""
        character.position = [
            feet[0] - character.rect.width / 2,
            feet[1] + character.feet.height / 2 - character.rect.height,
        ]
        character.update()

    def _teleport(self, technique, user=None, target=None):
        """Instant Transmission: reappear behind the closest foe (or target)
        and hit. user: the player unless an NPC uses it."""
        player = user or self.player
        reach = technique.stats["reach"]
        if target is None or target.hp <= 0:
            foes = self._targets if player is self.player else self.foes_of(player)
            candidates = [t for t in foes if t.hp > 0
                          and self._distance(player.feet.center, t.feet.center) <= reach]
            target = min(candidates, key=lambda t: self._distance(player.feet.center, t.feet.center),
                         default=None)
        old_position = list(player.position)
        if target is not None:
            # Behind the target if there is room, else beside it, else in front
            fx, fy = DIRECTION_VECTORS.get(target.facing, (0, 1))
            spots = [(-fx, -fy), (fy, fx), (-fy, -fx), (fx, fy)]
            # Far enough not to land in the target's body (Broly's is wide)
            side_gap = max(16, (target.body_width + player.body_width) / 2 + 2)
            others = solid_bodies(self._fighters, player)
            for sx, sy in spots:
                feet = (target.feet.centerx + sx * side_gap, target.feet.centery + sy * 12)
                self._place_feet(player, feet)
                if not any(player.feet.colliderect(wall) for wall in self._collisions) and \
                        player.body.collidelist(others) == -1:
                    break
            else:
                player.position = list(old_position)
            # Face the target
            dx = target.feet.centerx - player.feet.centerx
            dy = target.feet.centery - player.feet.centery
            if abs(dx) >= abs(dy):
                player.facing = AnimationDirection.RIGHT.value if dx >= 0 else AnimationDirection.LEFT.value
            else:
                player.facing = AnimationDirection.DOWN.value if dy >= 0 else AnimationDirection.UP.value
        else:
            dx, dy = DIRECTION_VECTORS[player.facing]
            player.position = [old_position[0] + dx * 60, old_position[1] + dy * 60]
        player.update()
        if any(player.feet.colliderect(wall) for wall in self._collisions):
            player.position = old_position  # would land in a wall: stay
            player.update()
        player.save_location()
        frames = player.get_frames(technique.pose_macro(player.facing))[::-1]
        damage = technique.damage * self._damage_multiplier(player)
        if player is not self.player:
            damage *= getattr(player, "technique_damage", 1.0)

        def strike():
            player.strike()
            if target is not None and target.hp > 0 and \
                    self._distance(player.feet.center, target.feet.center) <= \
                    self._reach(player, target, self.ATTACK_RANGE) + 12:
                target.take_damage(damage, player.feet.center, 2.0)

        player._play("teleport", frames, player.SPECIAL_CLOCK_SPEED, on_done=strike)

    def _player_attack_area(self):
        return self.player.feet.center, self.player.facing

    @classmethod
    def body_reach(cls, character):
        """Extra melee reach for a body bigger than the ordinary ones."""
        return max(0, character.rect.width - cls.STANDARD_BODY_WIDTH) * cls.BIG_BODY_REACH

    def _reach(self, a, b, base):
        return base + self.body_reach(a) + self.body_reach(b)

    def _is_in_attack_range(self, npc):
        origin, direction = self._player_attack_area()
        target = npc.feet.center
        forward, lateral = self._forward_lateral(direction, origin, target)
        lateral_tolerance = (
            self.player.feet.width + npc.feet.width
        ) / 2 + self.ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= self._reach(self.player, npc, self.ATTACK_RANGE) and abs(lateral) <= lateral_tolerance

    def _move_toward(self, npc, target, collisions):
        if npc.chase_path:
            target_cell = self._grid_cell(target)
            if self._distance(
                self._cell_to_feet_center(npc, npc.chase_target),
                self._cell_to_feet_center(npc, target_cell),
            ) > self.PATH_GRID_SIZE * 3:
                npc.chase_path = []
                npc.chase_target = None

        if npc.chase_path:
            waypoint = self._cell_to_feet_center(npc, npc.chase_path[0])
            if self._distance(npc.feet.center, waypoint) <= self.PATH_GRID_SIZE:
                npc.chase_path.pop(0)
            if npc.chase_path:
                waypoint = self._cell_to_feet_center(npc, npc.chase_path[0])
                self._step_toward(npc, waypoint, collisions)
                return

        starting_position = tuple(npc.position)
        self._step_toward(npc, target, collisions)
        if self._distance(starting_position, npc.position) < 0.01:
            npc.chase_stuck_frames += 1
        else:
            npc.chase_stuck_frames = 0

        if npc.chase_stuck_frames >= 4:
            npc.chase_path = self._find_path(npc, target, collisions)
            npc.chase_target = self._grid_cell(target)
            npc.chase_stuck_frames = 0
            if npc.chase_path:
                waypoint = self._cell_to_feet_center(npc, npc.chase_path[0])
                self._step_toward(npc, waypoint, collisions)
            elif hasattr(npc, "unreachable_until"):
                # No way there (across water, behind a wall): instead of
                # pushing against the obstacle forever, leave it for a while
                npc.unreachable_until = pygame.time.get_ticks() + self.UNREACHABLE_MS

    def _step_toward(self, npc, target, collisions):
        dx = target[0] - npc.feet.centerx
        dy = target[1] - npc.feet.centery
        if abs(dx) < 0.01 and abs(dy) < 0.01:
            return
        direction = (
            AnimationDirection.RIGHT.value if dx >= 0 else AnimationDirection.LEFT.value
        ) if abs(dx) >= abs(dy) else (
            AnimationDirection.DOWN.value if dy >= 0 else AnimationDirection.UP.value
        )
        npc.move(f"Walk {direction}", 4, (dx, dy))
        npc.update()
        resolve_movement_collisions(npc, collisions, solid_bodies(self._fighters, npc))

    def _npc_in_attack_range(self, npc):
        """Whether npc's punch reaches its target (the player if none)."""
        foe = npc.target or self.player
        origin = npc.feet.center
        target = foe.feet.center
        forward, lateral = self._forward_lateral(npc.facing, origin, target)
        tolerance = (
            foe.feet.width + npc.feet.width
        ) / 2 + self.NPC_ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= self._reach(npc, foe, self.NPC_ATTACK_RANGE) and abs(lateral) <= tolerance

    @staticmethod
    def _forward_lateral(direction, origin, target):
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

    def _find_path(self, npc, target, collisions):
        start = self._grid_cell(npc.feet.center)
        target_cell = self._grid_cell(target)
        bounds = self._path_bounds(npc, target, collisions)
        frontier = [(0, start)]
        came_from = {start: None}
        cost_so_far = {start: 0}
        goal = None

        while frontier:
            _, current = heapq.heappop(frontier)
            if self._cell_within_attack_range(npc, current, target):
                goal = current
                break

            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                neighbor = (current[0] + dx, current[1] + dy)
                if not self._cell_in_bounds(neighbor, bounds):
                    continue
                if not self._cell_is_walkable(npc, neighbor, collisions):
                    continue

                new_cost = cost_so_far[current] + 1
                if neighbor in cost_so_far and new_cost >= cost_so_far[neighbor]:
                    continue
                cost_so_far[neighbor] = new_cost
                heuristic = abs(neighbor[0] - target_cell[0]) + abs(neighbor[1] - target_cell[1])
                heapq.heappush(frontier, (new_cost + heuristic, neighbor))
                came_from[neighbor] = current

        if goal is None:
            return []

        path = []
        current = goal
        while current != start:
            path.append(current)
            current = came_from[current]
        path.reverse()
        return path

    def _cell_within_attack_range(self, npc, cell, target):
        center = self._cell_to_feet_center(npc, cell)
        dx = target[0] - center[0]
        dy = target[1] - center[1]
        lateral_tolerance = self.NPC_ATTACK_LATERAL_TOLERANCE
        reach = self._reach(npc, npc.target or self.player, self.NPC_ATTACK_RANGE)
        return (
            math.hypot(dx, dy) <= reach
            and abs(dx) <= reach + lateral_tolerance
            and abs(dy) <= reach + lateral_tolerance
        )

    def _cell_is_walkable(self, npc, cell, collisions):
        # collidelist tests every wall in C: a search visits thousands of cells
        return self._feet_at_position(npc, self._cell_to_position(npc, cell)).collidelist(collisions) == -1

    def _path_bounds(self, npc, target, collisions):
        points_x = [npc.feet.centerx, target[0]]
        points_y = [npc.feet.centery, target[1]]
        for obstacle in collisions:
            points_x.extend((obstacle.left, obstacle.right))
            points_y.extend((obstacle.top, obstacle.bottom))
        grid = self.PATH_GRID_SIZE
        return (
            math.floor(min(points_x) / grid) - 2,
            math.floor(max(points_x) / grid) + 2,
            math.floor(min(points_y) / grid) - 2,
            math.floor(max(points_y) / grid) + 2,
        )

    @staticmethod
    def _grid_cell(point):
        grid = CombatSystem.PATH_GRID_SIZE
        return round(point[0] / grid), round(point[1] / grid)

    def _cell_to_feet_center(self, npc, cell):
        return cell[0] * self.PATH_GRID_SIZE, cell[1] * self.PATH_GRID_SIZE

    def _cell_to_position(self, npc, cell):
        center_x, center_y = self._cell_to_feet_center(npc, cell)
        return (
            center_x - npc.rect.width / 2,
            center_y - npc.rect.height + npc.feet.height / 2,
        )

    def _feet_at_position(self, npc, position):
        x, y = position
        return pygame.Rect(
            x + (npc.rect.width - npc.feet.width) / 2,
            y + npc.rect.height - npc.feet.height,
            npc.feet.width,
            npc.feet.height,
        )

    @staticmethod
    def _cell_in_bounds(cell, bounds):
        min_x, max_x, min_y, max_y = bounds
        return min_x <= cell[0] <= max_x and min_y <= cell[1] <= max_y

    @staticmethod
    def _distance(first, second):
        return math.hypot(first[0] - second[0], first[1] - second[1])

    def draw(self, screen):
        self._draw_bar(screen, "HP", self.player.hp, self.player.max_hp, self.HP_COLOR, 20)
        ki_color = self.SUPER_COLOR if self.player.powered_up else (65, 145, 245)
        self._draw_bar(screen, "KI", self.player.ki, self.player.max_ki, ki_color, 58)
        technique = self.technique
        if technique is not None:
            # Selected technique and its cost, dimmed while there is not enough ki
            color = (255, 230, 120) if self.player.ki >= technique.cost else (150, 150, 160)
            label = self._label(f"{technique.name} ({technique.cost} KI)", self.name_font, color)
            screen.blit(label, (62, 88))

    NPC_BAR_MIN_WIDTH = 120
    NPC_BAR_HEIGHT = 14
    NPC_BAR_GAP = 8
    SUPER_COLOR = (245, 205, 60)
    # Health bars (the player's and the enemies')
    HP_COLOR = (70, 200, 90)
    FRAME_COLOR = (235, 235, 235)
    ALLY_COLOR = (120, 195, 255)

    def _label(self, text, font, color=(255, 255, 255)):
        key = (text, font, color)
        label = self._labels.get(key)
        if label is None:
            label = self._labels[key] = font.render(text, True, color)
        return label

    def draw_npc_bars(self, screen, npcs, to_screen_rect):
        """Draw a health bar above each NPC.

        to_screen_rect converts a rect in map coordinates to screen coordinates.
        The bar stays (empty) during the knock-out animation, then disappears.
        """
        for npc in npcs:
            if npc.faint_finished:
                continue
            on_screen = pygame.Rect(to_screen_rect(npc.rect))
            width = max(self.NPC_BAR_MIN_WIDTH, on_screen.width)
            bar = pygame.Rect(0, 0, width, self.NPC_BAR_HEIGHT)
            bar.midbottom = (on_screen.centerx, on_screen.top - self.NPC_BAR_GAP)
            fraction = max(0, min(1, npc.hp / npc.max_hp)) if npc.max_hp else 0
            pygame.draw.rect(screen, (35, 35, 42), bar)
            pygame.draw.rect(
                screen,
                self.HP_COLOR,
                (bar.x, bar.y, round(bar.width * fraction), bar.height),
            )
            # Gold frame while the NPC is a Super Saiyan; allies in blue
            ally = getattr(npc, "team", None) == HEROES
            frame_color = self.SUPER_COLOR if npc.powered_up else (self.ALLY_COLOR if ally else self.FRAME_COLOR)
            pygame.draw.rect(screen, frame_color, bar, 2)
            label = getattr(npc, "bar_label", None) or npc.character_name.capitalize()
            name = self._label(label, self.name_font, self.ALLY_COLOR if ally else (255, 255, 255))
            screen.blit(name, name.get_rect(midbottom=(bar.centerx, bar.top - 2)))

    def _draw_bar(self, screen, label, value, maximum, color, y):
        x = 20
        bar_width = min(260, self.screen_size[0] // 3)
        bar_height = 22
        screen.blit(self._label(label, self.font), (x, y))
        bar_x = x + 42
        bar_y = y + 3
        pygame.draw.rect(screen, (35, 35, 42), (bar_x, bar_y, bar_width, bar_height))
        fraction = max(0, min(1, value / maximum)) if maximum else 0
        pygame.draw.rect(
            screen,
            color,
            (bar_x, bar_y, round(bar_width * fraction), bar_height),
        )
        pygame.draw.rect(screen, self.FRAME_COLOR, (bar_x, bar_y, bar_width, bar_height), 2)
