import pygame

from animation import Animation, AnimationDirection, AnimationType
from constants import C_FAINT_ANIMATION_COUNT
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
    # A character that just flinched shrugs off hits for a moment, so a fast
    # attacker cannot keep it stunned forever
    FLINCH_COOLDOWN_MS = 500
    # Time between two strikes: the same for the player and the NPCs
    ATTACK_COOLDOWN_MS = 400

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

    def revert(self):
        """Back to the base form."""
        if self.is_super:
            self.set_form(self.BASE_FORM)
            self.face_idle()

    # ---- Damage -----------------------------------------------------------------
    def take_damage(self, amount):
        amount *= self.damage_taken
        if self.is_super:
            amount *= self.SUPER_DAMAGE_TAKEN
        self.hp = max(0, self.hp - amount)
        if amount > 0 and self.hp > 0:
            self._flinch()
        return amount

    def _flinch(self):
        # Not while transforming, and not again right after the last flinch
        if self.action is not None and self.action["name"] == "transform":
            return
        now = pygame.time.get_ticks()
        if self.last_flinch_ms is not None and now - self.last_flinch_ms < self.FLINCH_COOLDOWN_MS:
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
        frames = []
        for index in range(C_FAINT_ANIMATION_COUNT):
            name = f"Faint {index}"
            if not self.has_animation(name):
                return []
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
