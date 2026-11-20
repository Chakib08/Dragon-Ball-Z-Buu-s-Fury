"""The rules of a fight: who can hit whom, how hard, the player's punches
and special techniques (with charging), the effects flying around, ki.

Each frame, update() runs the fight: the player's attack, then every NPC's
turn, decided by its brain (npc_ai.py). What is drawn on top of the map
(bars, team panels) is the HUD's (hud.py).
"""

import math

import pygame

from character import DIRECTION_VECTORS
from effects import ChargeGlow, build_effect, effect_origin
from hud import CombatHud
from movement import solid_bodies
from npc import HEROES
from npc_ai import NpcBrain, direction_to, forward_lateral


class CombatSystem:
    # Melee reach in map pixels between the two characters' feet, the same
    # for the player and the NPCs: bodies (15-25 px wide) nearly touch
    ATTACK_RANGE = 22
    ATTACK_LATERAL_TOLERANCE = 8
    # Sprites up to this wide count as ordinary bodies; a bigger one (Broly)
    # adds this share of the extra width to the reach, for hitting him and
    # for his own hits, so fighters touching him can hit and be hit
    STANDARD_BODY_WIDTH = 32
    BIG_BODY_REACH = 0.4
    # One punch or kick per button press, at most one every
    # Character.ATTACK_COOLDOWN_MS (the pace NPCs strike at too)
    PLAYER_ATTACK_DAMAGE = 15
    KI_REGEN_PER_SECOND = 12
    NPC_KI_REGEN_PER_SECOND = 6
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
        # Called with (user, technique id, direction, origin, power) when the
        # player or one of his allies releases one (online play shows it to
        # the opponent)
        self.on_technique = None
        # A technique being charged (button held), see start_special
        self.charge = None
        # As of the last update: who the player's side can hit (targets),
        # the player's side (heroes), everyone on the field and the walls
        self.targets = []
        self.heroes = [player]
        self.fighters = [player]
        self.collisions = []
        self.ai = NpcBrain(self)
        self.hud = CombatHud(self)

    def update(self, npcs, collisions, player_attacking=False, opponents=()):
        """One frame of combat. npcs are fought by their brains (npc_ai.py):
        enemies fight the player and his allies, allies (team HEROES) fight
        the enemies. opponents (online players) are only targets for the
        player's hits."""
        now = pygame.time.get_ticks()
        elapsed_seconds = max(0, now - self.last_update_ms) / 1000
        self.last_update_ms = now
        self._update_ki(npcs, elapsed_seconds)
        enemies = [npc for npc in npcs if npc.team != HEROES]
        allies = [npc for npc in npcs if npc.team == HEROES]
        # What the player, and his allies' and his techniques, can hit
        self.targets = [*enemies, *opponents]
        self.collisions = collisions
        self.heroes = [self.player, *allies]
        # Everyone on the field: their bodies block each other
        self.fighters = [self.player, *npcs, *opponents]
        self._update_charge()
        self._update_effects()

        self.player_swung = False
        self.player.update_knockback(collisions, solid_bodies(self.fighters, self.player))
        if self.player.hp <= 0:
            self.player.faint()
        elif player_attacking:
            self._player_attack(self.targets, now)

        for npc in tuple(npcs):
            self.ai.update(npc, now, collisions)

    def _update_ki(self, npcs, elapsed_seconds):
        """Ki comes back over time; a Super Saiyan burns it instead."""
        player = self.player
        if player.can_revert:
            drain = self.SUPER_KI_DRAIN_PER_SECOND.get(player.form, 1)
            player.ki = max(0, player.ki - drain * elapsed_seconds)
            if player.ki <= 0:
                player.revert()
        else:
            player.ki = min(player.max_ki, player.ki + self.KI_REGEN_PER_SECOND * elapsed_seconds)
        for npc in npcs:
            npc.ki = min(npc.max_ki, npc.ki + self.NPC_KI_REGEN_PER_SECOND * elapsed_seconds)

    @property
    def allies(self):
        return self.heroes[1:]

    @property
    def enemies(self):
        return list(self.targets)

    # ---- Reach --------------------------------------------------------------------
    @classmethod
    def body_reach(cls, character):
        """Extra melee reach for a body bigger than the ordinary ones."""
        return max(0, character.rect.width - cls.STANDARD_BODY_WIDTH) * cls.BIG_BODY_REACH

    def reach(self, a, b, base=None):
        """How far apart a's and b's feet can be for a punch to land."""
        return (self.ATTACK_RANGE if base is None else base) + self.body_reach(a) + self.body_reach(b)

    def _is_in_attack_range(self, npc):
        """Whether the player's punch reaches npc (in front of him)."""
        player = self.player
        forward, lateral = forward_lateral(player.facing, player.feet.center, npc.feet.center)
        lateral_tolerance = (player.feet.width + npc.feet.width) / 2 + self.ATTACK_LATERAL_TOLERANCE
        return 0 <= forward <= self.reach(player, npc) and abs(lateral) <= lateral_tolerance

    # ---- Punches and kicks --------------------------------------------------------
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
        target = min(targets, key=lambda npc: math.dist(player.rect.center, npc.rect.center))
        target.take_damage(
            self.PLAYER_ATTACK_DAMAGE * self.damage_multiplier(player), player.feet.center
        )

    def damage_multiplier(self, attacker):
        """The attacker's power (Config/stats.json), times its Super Saiyan bonus."""
        return getattr(attacker, "power", 1.0) * self._super_multiplier(attacker)

    def _super_multiplier(self, attacker):
        if not attacker.powered_up:
            return 1
        if attacker is self.player:
            if attacker.form == attacker.SUPER_3_FORM:
                return self.SUPER_3_DAMAGE_MULTIPLIER
            return self.SUPER_DAMAGE_MULTIPLIER
        return self.NPC_SUPER_DAMAGE_MULTIPLIER


    # ---- Techniques of anyone but the player (the NPCs' brains use them) --------
    def use_technique(self, user, technique, target=None):
        """An NPC (or any character but the player, who uses start_special)
        uses a technique towards target: its pose, then the effect. Charged
        techniques go off at three quarters of their power."""
        if user.hp <= 0 or user.action is not None:
            return False
        direction = user.facing if target is None else direction_to(user.feet.center, target.feet.center)
        user.facing = direction
        sprites = technique.form_for(user)
        frames = user.frames(technique.pose_macro(direction))
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
        frames = player.frames(technique.pose_macro(facing))
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
        glow = ChargeGlow(glow_frames, player, technique.effect_scale) if glow_frames else None
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
        self.hud.draw_charge(screen, to_screen_rect)

    def _hit_target(self, target, damage, source, push):
        target.take_damage(damage, source, push)

    def _release(self, technique, direction, power=None):
        """The player's pose reached its firing frame (see _release_by)."""
        self._release_by(self.player, technique, direction, power)

    def _release_by(self, user, technique, direction, power=None):
        """The pose reached its firing frame: the effect leaves user's hands,
        towards the other side. power: how charged it was (0 to 1); a tap
        does half the damage. An NPC's technique does a share of it (see
        difficulty.py)."""
        if user.hp <= 0:
            return None
        damage = technique.damage * self.damage_multiplier(user)
        if user is not self.player:
            damage *= getattr(user, "technique_damage", 1.0)
        if power is not None:
            damage *= 0.5 + 0.5 * power
        effect = build_effect(technique, technique.form_for(user), user, direction,
                              damage, self._hit_target, self.add_effect, power=power)
        if effect is not None:
            effect.team = user.team
            self.add_effect(effect)
            if self.on_technique is not None and user.team == HEROES:
                self.on_technique(user, technique.id, direction, effect_origin(effect, user, direction), power)
        return effect

    def show_opponent_technique(self, opponent, technique_id, direction, origin, power=None):
        """Draw a technique the online opponent (or one of its allies) used.
        It stops on the player's side but does no damage here: the
        opponent's game sends the hit."""
        technique = next((t for t in opponent.techniques if t.id == technique_id), None)
        if technique is None or technique.kind == "teleport" or direction not in DIRECTION_VECTORS:
            return
        effect = build_effect(technique, technique.form_for(opponent), opponent, direction,
                              0, None, self.add_effect, origin=origin, power=power)
        if effect is not None:
            effect.from_opponent = True
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
            if getattr(effect, "from_opponent", False):
                victims = self.heroes  # drawn for the online opponent
            elif getattr(effect, "team", HEROES) == HEROES:
                victims = self.targets
            else:
                victims = self.heroes
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
            foes = self.targets if player is self.player else self.ai.foes_of(player)
            candidates = [t for t in foes if t.hp > 0
                          and math.dist(player.feet.center, t.feet.center) <= reach]
            target = min(candidates, key=lambda t: math.dist(player.feet.center, t.feet.center),
                         default=None)
        old_position = list(player.position)
        if target is not None:
            # Behind the target if there is room, else beside it, else in front
            fx, fy = DIRECTION_VECTORS.get(target.facing, (0, 1))
            spots = [(-fx, -fy), (fy, fx), (-fy, -fx), (fx, fy)]
            # Far enough not to land in the target's body (Broly's is wide)
            side_gap = max(16, (target.body_width + player.body_width) / 2 + 2)
            others = solid_bodies(self.fighters, player)
            for sx, sy in spots:
                feet = (target.feet.centerx + sx * side_gap, target.feet.centery + sy * 12)
                self._place_feet(player, feet)
                if not any(player.feet.colliderect(wall) for wall in self.collisions) and \
                        player.body.collidelist(others) == -1:
                    break
            else:
                player.position = list(old_position)
            # Face the target
            player.facing = direction_to(player.feet.center, target.feet.center)
        else:
            dx, dy = DIRECTION_VECTORS[player.facing]
            player.position = [old_position[0] + dx * 60, old_position[1] + dy * 60]
        player.update()
        if any(player.feet.colliderect(wall) for wall in self.collisions):
            player.position = old_position  # would land in a wall: stay
            player.update()
        player.save_location()
        frames = player.frames(technique.pose_macro(player.facing))[::-1]
        damage = technique.damage * self.damage_multiplier(player)
        if player is not self.player:
            damage *= getattr(player, "technique_damage", 1.0)

        def strike():
            player.strike()
            if target is not None and target.hp > 0 and \
                    math.dist(player.feet.center, target.feet.center) <= \
                    self.reach(player, target) + 12:
                target.take_damage(damage, player.feet.center, 2.0)

        player._play("teleport", frames, player.SPECIAL_CLOCK_SPEED, on_done=strike)

    # ---- Drawing (see hud.py) -------------------------------------------------------
    def draw(self, screen):
        self.hud.draw(screen)

    def draw_team_panels(self, screen):
        return self.hud.draw_team_panels(screen)

    def draw_npc_bars(self, screen, npcs, to_screen_rect):
        return self.hud.draw_npc_bars(screen, npcs, to_screen_rect)
