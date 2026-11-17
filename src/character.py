import pygame

from animation import Animation, AnimationDirection, AnimationType
from constants import C_FAINT_ANIMATION_COUNT
from movement import resolve_movement_collisions
from utils.config import Config

DIRECTION_VECTORS = {
    AnimationDirection.RIGHT.value: (1, 0),
    AnimationDirection.LEFT.value: (-1, 0),
    AnimationDirection.DOWN.value: (0, 1),
    AnimationDirection.UP.value: (0, -1),
}


class Character(Animation):
    """A sprite that can move, fight, get hurt and be knocked out."""

    MAX_HP = 200
    MAX_KI = 100
    WALK_SPEED = 1
    RUN_SPEED = 2
    # Share of incoming damage that gets through (lower = tougher)
    DAMAGE_TAKEN = 1.0
    SUPER_DAMAGE_TAKEN = 0.5
    # Minimum time between two hurt animations (0: every hit). Nobody gets
    # stun-locked: the player acts out of a flinch with a button press, an
    # NPC when its next strike is due (see CombatSystem)
    FLINCH_COOLDOWN_MS = 0
    # Time between two strikes: the same for the player and the NPCs
    ATTACK_COOLDOWN_MS = 400

    # Pushed this many map pixels away from whoever lands a hit, spread over
    # KNOCKBACK_FRAMES frames (slowing down as it goes)
    KNOCKBACK_DISTANCE = 4
    KNOCKBACK_FRAMES = 6
    # Guarding halves the damage (the hit still pushes)
    BLOCK_DAMAGE_TAKEN = 0.5

    # Animation clock units added per frame (higher = faster animation)
    ATTACK_CLOCK_SPEED = 20
    HURT_CLOCK_SPEED = 12
    SPECIAL_CLOCK_SPEED = 16
    FAINT_CLOCK_SPEED = 8

    can_transform = False

    def __init__(self, pos_x, pos_y, name):
        super().__init__(name)
        self.speed = 0
        self.position = [pos_x, pos_y]
        self.old_position = self.position.copy()
        self.rect = self.image.get_rect()
        self.feet = pygame.Rect(0, 0, self.rect.width / 4, 4)
        self.facing = AnimationDirection.DOWN.value

        self.max_hp = self.MAX_HP
        self.hp = self.max_hp
        self.max_ki = self.MAX_KI
        self.ki = self.max_ki
        self.damage_taken = self.DAMAGE_TAKEN
        self.last_flinch_ms = None
        self._powered_up = False
        self.blocking = False
        # Remaining push from the last hit: (x step, y step, frames left)
        self.knockback = None
        # Which move of the attack combo comes next
        self.attack_move_index = 0

        # Short animation that locks the character (hurt, transform, special)
        self.action = None
        self.faint_frames = None
        self.faint_index = 0
        self.faint_clock = 0
        self.faint_finished = False

    # ---- Position -------------------------------------------------------------
    def update(self):
        self.rect.topleft = self.position
        self.feet.midbottom = self.rect.midbottom

    def save_location(self):
        self.old_position = self.position.copy()

    def image_offset(self):
        """Where to draw the current frame relative to the rect: frames have
        different sizes, so keep them centered with the feet on the ground."""
        return (
            (self.rect.width - self.image.get_width()) // 2,
            self.rect.height - self.image.get_height(),
        )

    # ---- Looping animations -----------------------------------------------------
    def face_idle(self, direction=None):
        """Stand still, facing the given (or current) direction."""
        if direction is not None:
            self.facing = direction
        self.reset_animation()
        self.animation_name = f"IDLE {self.facing}"
        self.image = self.get_image_by_animation_name(
            self.animation_name, flipped=self.facing == AnimationDirection.LEFT.value
        )

    def move(self, animation_macro, animation_count, movement=None):
        macro, side = animation_macro.split()
        self.facing = side
        self.clock_speed = Config.CLOCK_SPEED
        self.speed = self.RUN_SPEED if macro == AnimationType.RUN.value else self.WALK_SPEED

        if movement is None:
            movement = DIRECTION_VECTORS[side]
        length = (movement[0] ** 2 + movement[1] ** 2) ** 0.5
        if length == 0:
            return

        self.old_position = self.position.copy()
        self.position[0] += movement[0] / length * self.speed
        self.position[1] += movement[1] / length * self.speed
        self.animate(animation_macro, animation_count)

    def strike(self):
        """One attack move: a punch or a kick, the next one of the combo.

        Returns False if the character has no attack sprites.
        """
        moves = self.get_attack_moves(self.facing)
        if not moves:
            return False
        frames = moves[self.attack_move_index % len(moves)]
        self.attack_move_index += 1
        self._play("attack", frames, self.ATTACK_CLOCK_SPEED)
        return True

    # ---- Forms ------------------------------------------------------------------
    @property
    def is_super(self):
        return self.form == self.SUPER_FORM

    def transform(self):
        """Only characters that can transform do anything here (see saiyan.py)."""
        return False

    @property
    def powered_up(self):
        """Whether the Super Saiyan bonuses apply (more damage dealt, less
        taken). Transforming powers up; a character that only exists as a
        Super Saiyan looks the part but powers up separately (see power_up)."""
        return self.can_revert or self._powered_up

    def power_up(self):
        self._powered_up = True

    @property
    def can_revert(self):
        """False for a character that only exists as a Super Saiyan."""
        return self.is_super and self.has_form(self.BASE_FORM)

    def revert(self):
        """Back to the base form."""
        if self.can_revert:
            self.set_form(self.BASE_FORM)
            self.face_idle()

    # ---- Damage -----------------------------------------------------------------
    def take_damage(self, amount, source=None):
        """Lose health; source is the position the hit came from (it pushes
        the character away from there)."""
        amount *= self.damage_taken
        if self.powered_up:
            amount *= self.SUPER_DAMAGE_TAKEN
        if self.blocking:
            amount *= self.BLOCK_DAMAGE_TAKEN
        self.hp = max(0, self.hp - amount)
        if amount > 0 and source is not None:
            self.push_from(source)
        if amount > 0 and self.hp > 0 and not self.blocking:
            self._flinch()
        return amount

    def push_from(self, source, strength=1.0):
        dx = self.feet.centerx - source[0]
        dy = self.feet.centery - source[1]
        length = (dx * dx + dy * dy) ** 0.5
        if length == 0:
            # Same spot: push away from where the character is facing
            dx, dy = DIRECTION_VECTORS[self.facing]
            dx, dy, length = -dx, -dy, 1
        # The steps add up to the full distance: first frames move the most
        frames = self.KNOCKBACK_FRAMES
        first_step = 2 * self.KNOCKBACK_DISTANCE * strength / (frames + 1)
        self.knockback = (dx / length * first_step, dy / length * first_step, frames)

    def update_knockback(self, collisions):
        """Move one step of the current push. Returns True while being pushed."""
        if self.knockback is None:
            return False
        step_x, step_y, frames = self.knockback
        scale = frames / self.KNOCKBACK_FRAMES
        self.old_position = self.position.copy()
        self.position[0] += step_x * scale
        self.position[1] += step_y * scale
        self.update()
        resolve_movement_collisions(self, collisions)
        self.knockback = (step_x, step_y, frames - 1) if frames > 1 else None
        return True

    # ---- Blocking ---------------------------------------------------------------
    def start_block(self):
        """Guard: half the damage and no flinch while it is held.
        Returns False when the character cannot guard right now."""
        if self.hp <= 0 or self.action is not None:
            self.stop_block()
            return False
        if not self.blocking:
            self.blocking = True
            self.reset_animation()
        name = f"Block {self.facing} 0"
        if self.has_animation(name):
            self.animation_name = f"Block {self.facing}"
            self.image = self.get_image_by_animation_name(
                name, flipped=self.facing == AnimationDirection.LEFT.value
            )
        else:
            # No guard sprite in this form: hold the standing pose
            self.face_idle()
        return True

    def stop_block(self):
        if self.blocking:
            self.blocking = False
            self.face_idle()

    def _flinch(self):
        # Not while transforming, and not again right after the last flinch
        if self.action is not None and self.action["name"] == "transform":
            return
        now = pygame.time.get_ticks()
        if (
            self.FLINCH_COOLDOWN_MS
            and self.last_flinch_ms is not None
            and now - self.last_flinch_ms < self.FLINCH_COOLDOWN_MS
        ):
            return
        if self.start_action("hurt", f"Hurt {self.facing}", clock_speed=self.HURT_CLOCK_SPEED):
            self.last_flinch_ms = now

    # ---- One-shot actions (hurt, transform, special) ------------------------------
    def start_action(self, name, animation_macro, clock_speed, hold_ticks=0,
                     on_last_frame=None, on_done=None):
        """Play "<macro> 0..n" once. Returns False if the frames are missing.

        on_last_frame fires when the last frame appears, on_done when the
        action is over (after the last frame was held for hold_ticks).
        """
        frames = self.get_frames(animation_macro)
        if not frames:
            return False
        self._play(name, frames, clock_speed, hold_ticks, on_last_frame, on_done)
        return True

    def _play(self, name, frames, clock_speed, hold_ticks=0, on_last_frame=None, on_done=None):
        self.action = {
            "name": name,
            "frames": frames,
            "index": 0,
            "clock": 0,
            "clock_speed": clock_speed,
            "hold_ticks": hold_ticks,
            "on_last_frame": on_last_frame,
            "on_done": on_done,
        }
        self.reset_animation()
        self.image = frames[0]
        if len(frames) == 1:
            self._fire_last_frame(self.action)

    def cancel_hurt(self):
        """Stop a hurt animation early (the player acting out of a flinch)."""
        if self.action is not None and self.action["name"] == "hurt":
            self.action = None
            self.face_idle()

    @staticmethod
    def _fire_last_frame(action):
        callback, action["on_last_frame"] = action["on_last_frame"], None
        if callback is not None:
            callback()

    def update_action(self):
        """Advance the running action. Returns True while the character is busy."""
        action = self.action
        if action is None:
            return False

        frames = action["frames"]
        last = len(frames) - 1
        self.image = frames[action["index"]]
        if action["index"] < last:
            action["clock"] += action["clock_speed"]
            if action["clock"] >= Config.CLOCK_LIMIT:
                action["clock"] = 0
                action["index"] += 1
                self.image = frames[action["index"]]
                if action["index"] == last:
                    self._fire_last_frame(action)
            return True

        if action["hold_ticks"] > 0:
            action["hold_ticks"] -= 1
            return True
        action["clock"] += action["clock_speed"]
        if action["clock"] < Config.CLOCK_LIMIT:
            return True

        self.action = None
        if action["on_done"] is not None:
            action["on_done"]()
        self.face_idle()
        return False

    # ---- Knock-out --------------------------------------------------------------
    def _load_faint_frames(self):
        flipped = self.facing == AnimationDirection.LEFT.value
        names = [f"Faint {index}" for index in range(C_FAINT_ANIMATION_COUNT)]
        if not all(self.has_animation(name) for name in names):
            # No knock-out sprites (e.g. a Super Saiyan only sheet): hold the
            # last hurt pose instead
            hurt = f"Hurt {self.facing}"
            count = self.frame_count(hurt)
            names = [f"{hurt} {count - 1}"] if count else []
        frames = []
        for name in names:
            frame = self.get_image_by_animation_name(name, flipped)
            # Pad the shorter "lying down" frames to the standing height
            colorkey = frame.get_colorkey()
            padded = pygame.Surface((frame.get_width(), max(self.rect.height, frame.get_height())))
            padded.fill(colorkey)
            padded.blit(frame, (0, padded.get_height() - frame.get_height()))
            padded.set_colorkey(colorkey)
            frames.append(padded)
        return frames

    def faint(self):
        """Play the knock-out animation once, then stay on the ground."""
        if self.faint_finished:
            return
        if self.faint_frames is None:
            # The knock-out sprites only exist in the base form
            self.action = None
            self.blocking = False
            self.set_form(self.BASE_FORM)
            self.reset_animation()
            self.faint_frames = self._load_faint_frames()
        if not self.faint_frames:
            # No knock-out sprites for this character: just stand still
            self.face_idle()
            self.faint_finished = True
            return

        self.animation_name = f"Faint {self.facing}"
        self.image = self.faint_frames[self.faint_index]
        if self.faint_index == len(self.faint_frames) - 1:
            self.faint_finished = True
            return
        self.faint_clock += self.FAINT_CLOCK_SPEED
        if self.faint_clock >= Config.CLOCK_LIMIT:
            self.faint_clock = 0
            self.faint_index += 1
