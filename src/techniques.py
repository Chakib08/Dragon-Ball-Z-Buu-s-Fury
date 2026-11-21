"""Special techniques (they cost ki), drawn with each character's own sprites.

Config/characters/<name>/specials.json lists a character's techniques. For
every form (base, ssj, ssj3) it gives sprite boxes: the poses on that form's
sheet, the effects on "sheet" when given (with its "background" colour, or
"auto" for a sheet of cells of different colours), else on the form's:

    pose        the character's poses per direction (Down, Right, Up), shown
                while the technique runs; "right_flip" when the sheet draws
                the sideways poses facing left
    fire_at     pose frame on which the effect is released
    projectile  flying frames, facing right (other directions are rotated)
    hit         spark played where it lands
    beam        either "full" frames (a whole beam: tail, body, head, cut by
                the "tail" and "head" widths) or separate "start", "body",
                "head" and "impact" pieces; "points_left" when the sheet
                draws the beam pointing left
    rings       a shockwave growing around the character
    grow        a ball growing in the hands before it flies
    vanish      teleport frames per direction (character -> gone)

The poses are added to the form's frames as "Tech <id> <direction> <i>", so
they play like any other animation and can be named to the other player in
online matches.
"""

import json
import os

import pygame

from animation import AnimationDirection, SpriteForm, load_sheet
from pathmanager import PathManager

DIRECTIONS = ("Down", "Right", "Left", "Up")

# Balance of each kind of technique (damage before the defender's own rules)
STATS = {
    "projectile": {"cost": 6, "damage": 30, "cooldown_ms": 500, "speed": 6, "range": 190},
    "beam": {"cost": 18, "damage": 75, "cooldown_ms": 1200, "speed": 9, "range": 230, "hold_ticks": 24},
    "teleport": {"cost": 12, "damage": 35, "cooldown_ms": 1000, "reach": 200},
    "burst": {"cost": 15, "damage": 45, "cooldown_ms": 1200, "radius": 46, "push": 4},
    "ball": {"cost": 20, "damage": 85, "cooldown_ms": 1500, "speed": 4, "range": 200},
    # Turns the user into another character: a Potara fusion, Cell
    # absorbing an android (see evolution.py)
    "evolve": {"cost": 40, "damage": 0, "cooldown_ms": 0},
}


def orient(image, direction, cache, key):
    """A right-facing effect frame turned towards direction (cached)."""
    cache_key = (key, direction)
    oriented = cache.get(cache_key)
    if oriented is None:
        if direction == AnimationDirection.RIGHT.value:
            oriented = image
        elif direction == AnimationDirection.LEFT.value:
            oriented = pygame.transform.flip(image, True, False)
        elif direction == AnimationDirection.UP.value:
            oriented = pygame.transform.rotate(image, 90)
        else:
            oriented = pygame.transform.rotate(image, -90)
        cache[cache_key] = oriented
    return oriented


_shades = {}


def background_shades(sheet):
    """The colours of a sheet's background: its three most common colours
    (the area around the frames and the two shades of their cells)."""
    shades = _shades.get(id(sheet))
    if shades is None:
        counts = {}
        width, height = sheet.get_size()
        for y in range(0, height, 2):
            for x in range(0, width, 2):
                colour = tuple(sheet.get_at((x, y)))[:3]
                counts[colour] = counts.get(colour, 0) + 1
        shades = _shades[id(sheet)] = sorted(counts, key=counts.get, reverse=True)[:3]
    return shades


class TechniqueForm:
    """A technique's sprites on one form's sheet."""

    def __init__(self, technique_id, data, sprite_form):
        self.data = data
        self.sprite_form = sprite_form
        # The effects can be on another sheet than the character's poses
        self.own_sheet = "sheet" in data
        if self.own_sheet:
            self.sheet = load_sheet(data["sheet"])
            # "auto": each frame on a cell of its own colour (the cells of
            # the sheet alternate two shades)
            self.background = None if data["background"] == "auto" else tuple(data["background"])
        else:
            self.sheet = sprite_form.sheet
            background = sprite_form.animations[0]["Background"]
            self.background = (background["R"], background["G"], background["B"])
        self._cache = {}
        self.fire_at = data.get("fire_at", 0)
        frames = data.get("pose") or data.get("vanish") or {}
        right_flip = frames.get("right_flip", False)
        for direction in DIRECTIONS:
            boxes = frames.get("Right" if direction == "Left" else direction, [])
            for index, box in enumerate(boxes):
                self._register(f"Tech {technique_id} {direction} {index}", box,
                               flip=right_flip and direction in ("Right", "Left"))

    def _register(self, name, box, flip=False):
        x, y, width, height = box
        frame = {"AnimationName": name, "x": x, "y": y, "Area Width": width, "Area Height": height,
                 "Size": {"Width": width, "Height": height}}
        # The pose's own cell colour: the sheets alternate two shades from
        # one cell to the next, and a corner of the box may be the sprite
        r, g, b = self._cell_background(x, y, width, height)
        frame["Background"] = {"R": r, "G": g, "B": b}
        if flip:
            frame["Flip"] = True
        self.sprite_form.frames_by_name.setdefault(name, frame)

    def _cell_background(self, x, y, width, height):
        """The most common colour of the box's four corners on the
        character's sheet."""
        sheet = self.sprite_form.sheet
        corners = []
        for px, py in ((x, y), (x + width - 1, y), (x, y + height - 1), (x + width - 1, y + height - 1)):
            if 0 <= px < sheet.get_width() and 0 <= py < sheet.get_height():
                corners.append(tuple(sheet.get_at((px, py)))[:3])
        return max(set(corners), key=corners.count) if corners else (0, 0, 0)

    def fire_frame(self, direction):
        fire_at = self.fire_at
        if isinstance(fire_at, dict):
            fire_at = fire_at.get("Right" if direction == "Left" else direction, 0)
        return fire_at

    def cut(self, box, flip=False):
        """The sprite in box, with the sheet's background transparent."""
        key = (tuple(box), flip)
        image = self._cache.get(key)
        if image is None:
            x, y, width, height = box
            image = pygame.Surface((width, height))
            image.blit(self.sheet, (0, 0), (x, y, width, height))
            image.set_colorkey(self.background or self._cell_colour(image))
            if flip:
                image = pygame.transform.flip(image, True, False)
            self._cache[key] = image
        return image

    def _cell_colour(self, image):
        """The background shade most present on the frame's border (a sprite
        can fill its cell up to the edges, so only shades of the sheet's
        background count)."""
        width, height = image.get_size()
        border = [tuple(image.get_at((x, y)))[:3] for x in range(width) for y in (0, height - 1)]
        border += [tuple(image.get_at((x, y)))[:3] for y in range(height) for x in (0, width - 1)]
        shades = background_shades(self.sheet)
        return max(shades, key=border.count)

    def cuts(self, name, flip=False):
        return [self.cut(box, flip) for box in self.data.get(name, [])]

    def oriented(self, image, direction):
        return orient(image, direction, self._cache, id(image))


class Technique:
    def __init__(self, data, character):
        self.id = data["id"]
        self.name = data["name"]
        self.kind = data["kind"]
        # A signature technique can be bigger than its kind's usual effect
        # ("effect_scale", the sprites) and reach farther ("range_scale",
        # flying as much faster, so it takes as long to get there)
        self.effect_scale = float(data.get("effect_scale", 1.0))
        range_scale = float(data.get("range_scale", 1.0))
        self.stats = dict(STATS[self.kind])
        for stat in ("range", "speed", "reach", "radius"):
            if stat in self.stats:
                self.stats[stat] = self.stats[stat] * range_scale
        self.cost = self.stats["cost"]
        self.damage = self.stats["damage"]
        self.forms = {
            form: TechniqueForm(self.id, form_data, character.forms[form])
            for form, form_data in data.get("forms", {}).items()
            if form in character.forms
        }
        # "evolve": who appears, how, and who the user becomes
        self.style = data.get("style")
        self.partner = data.get("partner")
        self.becomes = data.get("becomes")
        # A fusion's duration in seconds (None: for good, an absorption)
        self.lasts_s = data.get("lasts_s")
        # Seconds after a fusion splits before the fighter can fuse again
        self.cooldown_s = data.get("cooldown_s")

    def form_for(self, character):
        """Sprites for the character's current form (or any form it has)."""
        return self.forms.get(character.form) or next(iter(self.forms.values()), None)

    def pose_macro(self, direction):
        return f"Tech {self.id} {direction}"


def load_techniques(character):
    path = PathManager.character_json_path(character.character_name, "specials")
    if not os.path.exists(path):
        return []
    with open(path) as file:
        data = json.load(file)
    techniques = [Technique(entry, character) for entry in data.get("techniques", [])]
    return [technique for technique in techniques if technique.forms
            or (technique.kind == "evolve" and _has_sheets(technique.partner) and _has_sheets(technique.becomes))]


def _has_sheets(name):
    """Whether a character's sprite sheets are there (an evolution needs its
    partner's and its result's)."""
    if not name:
        return False
    paths = (PathManager.character_json_path(name, form) for form in ("base", "ssj"))
    return any(os.path.exists(path) and SpriteForm.sheet_exists(path) for path in paths)
