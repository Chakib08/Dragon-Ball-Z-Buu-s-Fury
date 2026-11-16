import pygame

from animation import Animation, AnimationDirection, AnimationType
from utils.config import Config
from constants import *

class Character(Animation):
    def __init__(self, pos_x, pos_y, json_file):
        super().__init__(json_file)
        
        # self.hp = hp
        # self.ki = ki
        self.speed = 0
        self.position = [pos_x, pos_y]
        self.rect = self.image.get_rect()
        self.feet = pygame.Rect(0, 0, self.rect.width / 4, 4)
        self.old_position = self.position.copy()
        self.max_hp = 100
        self.hp = self.max_hp
        self.max_ki = 100
        self.ki = self.max_ki
        self.facing = AnimationDirection.DOWN.value
        # Short animation that locks the character (hurt, transform, special)
        self.action = None
        self.faint_frames = None
        self.faint_index = 0
        self.faint_clock = 0
        self.faint_finished = False

    def update(self):
        self.rect.topleft = self.position
        self.feet.midbottom = self.rect.midbottom

    def move_back(self):
        self.position = self.old_position
        self.feet.midbottom = self.rect.midbottom
        #self.rect.topleft = self.rect.midbottom
    
    def move(self, animation_macro, animation_count, movement=None):
        macro, side = animation_macro.split()
        self.facing = side
        if macro == AnimationType.WALK.value:
            self.clock_speed = Config.CLOCK_SPEED
            self.speed = 1
        elif macro == AnimationType.RUN.value:
            self.clock_speed = Config.CLOCK_SPEED
            self.speed = 2

        if movement is None:
            movement = {
                AnimationDirection.RIGHT.value: (1, 0),
                AnimationDirection.LEFT.value: (-1, 0),
                AnimationDirection.DOWN.value: (0, 1),
                AnimationDirection.UP.value: (0, -1),
            }[side]

        length = (movement[0] ** 2 + movement[1] ** 2) ** 0.5
        if length == 0:
            return

        self.old_position = self.position.copy()
        self.position[0] += movement[0] / length * self.speed
        self.position[1] += movement[1] / length * self.speed

        self.animate(animation_macro, animation_count)
        
    def attack(self, animation_macro, animation_count):
        macro, side = animation_macro.split()
        self.facing = side
        if not self.has_animation(f"{animation_macro} 0"):
            self.images = []
            self.current_animation_macro = None
            self.current_animation_index = 0
            self.clock = 0
            self.image = self.get_image_by_animation_name(f"IDLE {side}")
            if side == AnimationDirection.LEFT.value:
                self.image = pygame.transform.flip(self.image, True, False)
            self.animation_name = f"IDLE {side}"
            return

        if macro is not None and macro == AnimationType.ATTACK.value:
            self.clock_speed = 20
        self.animate(animation_macro, animation_count)

    # Animation clock units added per frame while fainting (slower than a walk)
    FAINT_CLOCK_SPEED = 8

    def _load_faint_frames(self):
        frames = []
        for index in range(C_FAINT_ANIMATION_COUNT):
            name = f"Faint {index}"
            if not self.has_animation(name):
                return []
            frame = self.get_image_by_animation_name(name)
            if self.facing == "Left":
                frame = pygame.transform.flip(frame, True, False)
            # The sprite is drawn from the top-left of its rect, so pad the
            # shorter "lying down" frames to keep the body on the ground
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
            self.action = None
            self.set_form(self.BASE_FORM)
            self.faint_frames = self._load_faint_frames()
            self.images = []
            self.current_animation_macro = None
        if not self.faint_frames:
            # No knock-out sprites for this character: just stand still
            self._face_idle(self.facing)
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

    def _face_idle(self, direction):
        self.facing = direction
        self.image = self.get_image_by_animation_name(f"IDLE {direction}")
        if direction == "Left":
            self.image = pygame.transform.flip(self.image, True, False)

    def save_location(self):
        self.old_position = self.position.copy()

    def take_damage(self, amount):
        if self.is_super:
            amount *= self.SUPER_DAMAGE_TAKEN
        self.hp = max(0, self.hp - amount)
        # Flinch, unless knocked out (faint) or in the middle of transforming
        transforming = self.action is not None and self.action["name"] == "transform"
        if amount > 0 and self.hp > 0 and not transforming:
            self.start_action("hurt", f"Hurt {self.facing}", clock_speed=self.HURT_CLOCK_SPEED)

    # ---- Actions -----------------------------------------------------------
    HURT_CLOCK_SPEED = 12
    TRANSFORM_CLOCK_SPEED = 20
    SPECIAL_CLOCK_SPEED = 16
    TRANSFORM_MIN_KI = 20
    SUPER_DAMAGE_TAKEN = 0.5

    @property
    def is_super(self):
        return self.form == self.SUPER_FORM

    def image_offset(self):
        """Where to draw the current frame relative to the rect: frames have
        different sizes, so keep them centered with the feet on the ground."""
        return (
            (self.rect.width - self.image.get_width()) // 2,
            self.rect.height - self.image.get_height(),
        )

    def start_action(self, name, animation_macro, clock_speed, hold_ticks=0,
                     on_last_frame=None, on_done=None):
        """Play "<macro> 0..n" once. Returns False if the frames are missing."""
        count = self.frame_count(animation_macro)
        if count == 0:
            return False
        frames = [self.get_image_by_animation_name(f"{animation_macro} {i}") for i in range(count)]
        if AnimationDirection.LEFT.value in animation_macro:
            frames = [pygame.transform.flip(frame, True, False) for frame in frames]
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
        self.images = []
        self.current_animation_macro = None
        self.image = frames[0]
        if count == 1 and on_last_frame is not None:
            self.action["on_last_frame"] = None
            on_last_frame()
        return True

    def update_action(self):
        """Advance the running action. Returns True while the character is busy."""
        action = self.action
        if action is None:
            return False

        last = len(action["frames"]) - 1
        self.image = action["frames"][action["index"]]
        if action["index"] < last:
            action["clock"] += action["clock_speed"]
            if action["clock"] >= Config.CLOCK_LIMIT:
                action["clock"] = 0
                action["index"] += 1
                self.image = action["frames"][action["index"]]
                if action["index"] == last and action["on_last_frame"] is not None:
                    callback, action["on_last_frame"] = action["on_last_frame"], None
                    callback()
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
        self._face_idle(self.facing)
        return False

    def transform(self):
        """Toggle Super Saiyan. Returns True if something happened."""
        if self.action is not None or self.hp <= 0:
            return False
        if self.is_super:
            self.revert()
            return True
        if not self.has_form(self.SUPER_FORM) or self.ki < self.TRANSFORM_MIN_KI:
            return False

        def become_super():
            self.set_form(self.SUPER_FORM)
            self.facing = AnimationDirection.DOWN.value
            self.animation_name = "IDLE Down"

        if not self.start_action("transform", "Transform", self.TRANSFORM_CLOCK_SPEED,
                                 hold_ticks=10, on_done=become_super):
            become_super()
            self._face_idle(self.facing)
        return True

    def revert(self):
        """Back to the base form."""
        if not self.is_super:
            return
        self.set_form(self.BASE_FORM)
        self._face_idle(self.facing)
        