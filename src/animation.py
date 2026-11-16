import json
import os
from enum import Enum

import pygame

from pathmanager import PathManager
from utils.config import Config


class AnimationType(Enum):
    WALK = "Walk"
    RUN = "Run"
    ATTACK = "Attack"


class AnimationDirection(Enum):
    UP = "Up"
    DOWN = "Down"
    LEFT = "Left"
    RIGHT = "Right"


class SpriteForm:
    """One look of a character: a sprite sheet and the frames cut from it.

    Loaded once per JSON file and shared by every sprite that uses it, so a
    frame is cut out of the sheet (and mirrored) only the first time it is
    needed instead of on every game tick.
    """

    DEFAULT_ATTACK_MOVES = 4
    _cache = {}

    def __init__(self, json_file):
        with open(json_file) as file:
            data = json.load(file)
        self.character_name = data["Character"]
        self.sheet = pygame.image.load(os.path.join(Config.ROOT_DIR, data["Image path"]))
        self.animations = data["Animations"]
        # The "Attack" frames are a combo of this many moves (punches, kicks)
        self.attack_moves = data.get("Attack moves", self.DEFAULT_ATTACK_MOVES)
        # The first definition of a name wins, as it did with a list search
        self.frames_by_name = {}
        for frame in self.animations:
            self.frames_by_name.setdefault(frame["AnimationName"], frame)
        self._images = {}
        self._frame_counts = {}

    @classmethod
    def load(cls, json_file):
        form = cls._cache.get(json_file)
        if form is None:
            form = cls._cache[json_file] = cls(json_file)
        return form

    def has(self, animation_name):
        return animation_name in self.frames_by_name

    def frame_count(self, animation_macro):
        count = self._frame_counts.get(animation_macro)
        if count is None:
            count = 0
            while f"{animation_macro} {count}" in self.frames_by_name:
                count += 1
            self._frame_counts[animation_macro] = count
        return count

    def image(self, animation_name, flipped=False):
        """The frame as a surface. Shared: callers must not draw on it."""
        key = (animation_name, flipped)
        image = self._images.get(key)
        if image is None:
            image = self._images[key] = (
                pygame.transform.flip(self.image(animation_name), True, False)
                if flipped
                else self._cut(self.frames_by_name[animation_name])
            )
        return image

    def _cut(self, frame):
        size = (frame["Size"]["Width"], frame["Size"]["Height"])
        background = frame["Background"]
        image = pygame.Surface(size)
        image.blit(
            self.sheet,
            (0, 0),
            (frame["x"], frame["y"], frame["Area Width"], frame["Area Height"]),
        )
        image.set_colorkey((background["R"], background["G"], background["B"]))
        return image


class Animation(pygame.sprite.Sprite):
    BASE_FORM = "base"
    SUPER_FORM = "ssj"

    def __init__(self, name):
        super().__init__()
        # Every form uses the same animation names, so switching form only
        # swaps what gets drawn
        self.forms = {}
        for form in (self.BASE_FORM, self.SUPER_FORM):
            json_file = PathManager.character_json_path(name, form)
            if os.path.exists(json_file):
                self.forms[form] = SpriteForm.load(json_file)
        self.form = self.BASE_FORM
        self._sprites = self.forms[self.form]
        self.character_name = self._sprites.character_name

        self.current_animation_index = 0
        self.current_animation_macro = None
        self.animation_name = "IDLE Down"
        self.image = self.get_image_by_animation_name(self.animation_name)
        self.images = []
        self.rect = self.image.get_rect()
        self.clock = 0
        self.clock_speed = Config.CLOCK_SPEED

    # ---- Frames of the current form -----------------------------------------
    @property
    def sprit_sheet(self):
        return self._sprites.sheet

    @property
    def animations(self):
        return self._sprites.animations

    def get_animation_by_name(self, animation_name):
        return self._sprites.frames_by_name.get(animation_name)

    def has_animation(self, animation_name):
        return self._sprites.has(animation_name)

    def frame_count(self, animation_macro):
        """Number of frames named "<macro> 0", "<macro> 1", ..."""
        return self._sprites.frame_count(animation_macro)

    def get_image_by_animation_name(self, animation_name, flipped=False):
        return self._sprites.image(animation_name, flipped)

    def get_frames(self, animation_macro, count=None):
        """Frames "<macro> 0..count-1", mirrored for left-facing animations."""
        if count is None:
            count = self.frame_count(animation_macro)
        flipped = AnimationDirection.LEFT.value in animation_macro
        return [
            self._sprites.image(f"{animation_macro} {index}", flipped)
            for index in range(count)
        ]

    def get_attack_moves(self, direction):
        """The attack combo of a direction, split into its moves (one list
        of frames per punch or kick)."""
        frames = self.get_frames(f"{AnimationType.ATTACK.value} {direction}")
        moves = max(1, min(self._sprites.attack_moves, len(frames)))
        size = len(frames) // moves
        return [frames[index * size:(index + 1) * size] for index in range(moves)] if frames else []

    # ---- Forms ----------------------------------------------------------------
    def has_form(self, form):
        return form in self.forms

    def set_form(self, form):
        if form == self.form or form not in self.forms:
            return
        self.form = form
        self._sprites = self.forms[form]
        self.reset_animation()

    # ---- Looping animations (walk, run, attack) -------------------------------
    def reset_animation(self):
        self.images = []
        self.current_animation_macro = None
        self.current_animation_index = 0
        self.clock = 0

    def animate(self, animation_macro, animation_nbr):
        if self.current_animation_macro != animation_macro:
            self.images = self.get_frames(animation_macro, animation_nbr)
            self.current_animation_macro = animation_macro
            self.current_animation_index = 0
            self.clock = 0
        elif len(self.images) != animation_nbr:
            self.images = self.get_frames(animation_macro, animation_nbr)
            self.current_animation_index %= len(self.images)

        self.animation_name = animation_macro
        self.image = self.images[self.current_animation_index]

        self.clock += self.clock_speed
        if self.clock >= Config.CLOCK_LIMIT:
            self.current_animation_index = (self.current_animation_index + 1) % len(self.images)
            self.clock = 0

    def get_character_name(self):
        return self.character_name
