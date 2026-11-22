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


_sheets = {}


def load_sheet(path):
    """A sprite sheet image (relative to the game folder), loaded once."""
    sheet = _sheets.get(path)
    if sheet is None:
        sheet = _sheets[path] = pygame.image.load(os.path.join(Config.ROOT_DIR, path))
    return sheet


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
        self.sheet = load_sheet(data["Image path"])
        self.animations = data["Animations"]
        # The "Attack" frames are a combo of this many moves (punches, kicks)
        self.attack_moves = data.get("Attack moves", self.DEFAULT_ATTACK_MOVES)
        # Sheets drawn bigger than the others: every frame is shrunk this much
        self.scale = float(data.get("Scale", 1.0))
        # Colours that are never the character (a sheet whose frames sit in
        # boxes on another background): made transparent in every frame
        self.clear = [tuple(colour) for colour in data.get("Clear", [])]
        # The first definition of a name wins, as it did with a list search
        self.frames_by_name = {}
        for frame in self.animations:
            self.frames_by_name.setdefault(frame["AnimationName"], frame)
        self._images = {}
        # id of a cached frame -> (animation name, flipped): lets a sprite say
        # which frame it shows (online play sends that to the other player)
        self._frame_keys = {}
        self._frame_counts = {}

    @staticmethod
    def sheet_exists(json_file):
        """Whether the image this form is cut from is present (sheets are
        downloaded by setup.sh, so one may be missing)."""
        with open(json_file) as file:
            image_path = json.load(file)["Image path"]
        return os.path.exists(os.path.join(Config.ROOT_DIR, image_path))

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
            self._frame_keys[id(image)] = key
        return image

    def frame_key(self, image):
        """(animation name, flipped) of a frame this form produced, else None."""
        return self._frame_keys.get(id(image))

    def anchor_shift(self, image):
        """(dx, dy) to draw a frame this form produced at, from its usual
        place (centred, feet at the bottom): a pose from another sheet
        whose feet are off its centre ("Anchor X": where they are) or with
        a blade below them ("Below": how far it hangs). (0, 0) otherwise."""
        key = self._frame_keys.get(id(image))
        frame = self.frames_by_name.get(key[0]) if key else None
        if not frame:
            return 0, 0
        dx = 0
        anchor = frame.get("Anchor X")
        if anchor is not None:
            width = frame["Area Width"]
            mirrored = bool(frame.get("Flip")) != key[1]
            feet = width - anchor if mirrored else anchor
            dx = round((width / 2 - feet) * self.scale)
        return dx, round(frame.get("Below", 0) * self.scale)

    def _cut(self, frame):
        size = (frame["Size"]["Width"], frame["Size"]["Height"])
        # A frame can come from another sheet (e.g. an aura only drawn there)
        sheet = load_sheet(frame["Sheet"]) if "Sheet" in frame else self.sheet
        background = frame.get("Background")
        if background is None:
            # The colour around the sprite (sheets made of cells of two shades)
            colour = sheet.get_at((frame["x"], frame["y"]))[:3]
        else:
            colour = (background["R"], background["G"], background["B"])
        image = pygame.Surface(size)
        image.fill(colour)
        image.blit(
            sheet,
            (0, 0),
            (frame["x"], frame["y"], frame["Area Width"], frame["Area Height"]),
        )
        if self.clear:
            pixels = pygame.PixelArray(image)
            for other in self.clear:
                pixels.replace(other, colour)
            del pixels
        image.set_colorkey(colour)
        if self.scale != 1.0:
            # Smoothly, with see-through edges (not a fringe of the
            # background colour)
            clear = pygame.Surface(size, pygame.SRCALPHA)
            clear.blit(image, (0, 0))
            image = pygame.transform.smoothscale(
                clear, (max(1, round(size[0] * self.scale)), max(1, round(size[1] * self.scale))))
        # Some sheets draw a pose facing the other way than the game needs
        if frame.get("Flip"):
            image = pygame.transform.flip(image, True, False)
        return image


class Animator:
    """What a character looks like right now: its forms (sprite sheets), the
    current one, the frame shown (image) and the clock of the looping
    animation (walk, run). A component: Character owns one (self.animator)
    and decides when it moves, gets hurt or transforms; this only picks
    frames. It needs no position and is not a pygame sprite, so the menu
    can use one just for a preview.
    """

    BASE_FORM = "base"
    SUPER_FORM = "ssj"
    SUPER_2_FORM = "ssj2"
    SUPER_3_FORM = "ssj3"
    # Super Saiyan Blue (Vegito)
    SUPER_BLUE_FORM = "ssjb"
    # Super Saiyan levels, weakest first
    SUPER_FORMS = (SUPER_FORM, SUPER_2_FORM, SUPER_3_FORM, SUPER_BLUE_FORM)

    def __init__(self, name):
        # Every form uses the same animation names, so switching form only
        # swaps what gets drawn
        self.forms = {}
        for form in (self.BASE_FORM, *self.SUPER_FORMS):
            json_file = PathManager.character_json_path(name, form)
            if os.path.exists(json_file) and SpriteForm.sheet_exists(json_file):
                self.forms[form] = SpriteForm.load(json_file)
        if not self.forms:
            raise FileNotFoundError(
                f"No sprite sheet for {name}: run ./setup.sh to download them"
            )
        # A character with only a Super Saiyan sheet is always a Super Saiyan
        self.form = self.BASE_FORM if self.BASE_FORM in self.forms else self.SUPER_FORM
        self.sprites = self.forms[self.form]
        self.character_name = self.sprites.character_name

        self.current_animation_index = 0
        self.current_animation_macro = None
        self.animation_name = "IDLE Down"
        self.image = self.image_by_name(self.animation_name)
        self.images = []
        self.clock = 0.0

    # ---- Frames of the current form -----------------------------------------
    def image_by_name(self, animation_name, flipped=False):
        return self.sprites.image(animation_name, flipped)

    def has_animation(self, animation_name):
        return self.sprites.has(animation_name)

    def frame_count(self, animation_macro):
        """Number of frames named "<macro> 0", "<macro> 1", ..."""
        return self.sprites.frame_count(animation_macro)

    def frames(self, animation_macro, count=None):
        """Frames "<macro> 0..count-1", mirrored for left-facing animations."""
        if count is None:
            count = self.frame_count(animation_macro)
        flipped = AnimationDirection.LEFT.value in animation_macro
        return [
            self.sprites.image(f"{animation_macro} {index}", flipped)
            for index in range(count)
        ]

    def attack_moves(self, direction):
        """The attack combo of a direction, split into its moves (one list
        of frames per punch or kick)."""
        frames = self.frames(f"{AnimationType.ATTACK.value} {direction}")
        moves = max(1, min(self.sprites.attack_moves, len(frames)))
        size = len(frames) // moves
        return [frames[index * size:(index + 1) * size] for index in range(moves)] if frames else []

    def frame_key(self, image=None):
        """(animation name, flipped) of the frame shown (or of image), or
        None for a frame made elsewhere (a padded knock-out pose)."""
        return self.sprites.frame_key(self.image if image is None else image)

    def anchor_shift(self, image=None):
        """Where the frame shown (or image) is drawn from its usual place
        (see SpriteForm.anchor_shift)."""
        return self.sprites.anchor_shift(self.image if image is None else image)

    # ---- Forms ----------------------------------------------------------------
    def has_form(self, form):
        return form in self.forms

    def set_form(self, form):
        if form == self.form or form not in self.forms:
            return
        self.form = form
        self.sprites = self.forms[form]
        self.reset()

    # ---- Looping animations (walk, run, attack) -------------------------------
    def reset(self):
        self.images = []
        self.current_animation_macro = None
        self.current_animation_index = 0
        self.clock = 0.0

    def show(self, animation_name, flipped=False, frame=None):
        """Hold one frame: frame (a frame's name), else the one named
        animation_name (standing poses are named "IDLE Down"...)."""
        self.animation_name = animation_name
        self.image = self.image_by_name(frame or animation_name, flipped)

    def loop(self, animation_macro, animation_nbr, clock_speed, ticks=1.0):
        """Show the looping animation, advanced by ticks frames' worth of
        time (see utils.timing)."""
        if self.current_animation_macro != animation_macro:
            self.images = self.frames(animation_macro, animation_nbr)
            self.current_animation_macro = animation_macro
            self.current_animation_index = 0
            self.clock = 0.0
        elif len(self.images) != animation_nbr:
            self.images = self.frames(animation_macro, animation_nbr)
            self.current_animation_index %= len(self.images)

        self.animation_name = animation_macro
        self.image = self.images[self.current_animation_index]

        self.clock += clock_speed * ticks
        if self.clock >= Config.CLOCK_LIMIT:
            self.current_animation_index = (self.current_animation_index + 1) % len(self.images)
            self.clock = 0.0
