"""Special technique effects (energy blasts, beams, ki balls, shockwaves).

Effects are sprites in map coordinates: the map draws and zooms them with
the characters. Each one is advanced once per frame with update_effect(),
given the characters it can hit. Hitting calls on_hit(target, damage,
source, push); an effect cast by the online opponent has no on_hit: it only
stops on the player (its own game applies the damage).
"""

import math

import pygame

from character import DIRECTION_VECTORS
from contact import drawn_rect, effect_touches
from utils import timing

EFFECT_LAYER = 2
# The characters' layer (an aura is drawn with them, just behind its fighter)
CHARACTER_LAYER = 1


class Effect(pygame.sprite.Sprite):
    FRAME_TICKS = 4

    def __init__(self):
        super().__init__()
        self.done = False
        self.ticks = 0
        self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        self.rect = self.image.get_rect()

    def update_effect(self, targets):
        """Advance one frame; set done when finished."""

    def tick(self):
        """Count this frame (in 60 FPS frames, see utils.timing)."""
        self.ticks += timing.ticks()

    def frame_number(self, ticks_per_frame=None):
        return int(self.ticks // (ticks_per_frame or self.FRAME_TICKS))

    @staticmethod
    def _alive(targets):
        return [target for target in targets if target.hp > 0]


class Spark(Effect):
    """Hit spark (or explosion) played once."""

    def __init__(self, frames, center):
        super().__init__()
        self.frames = frames
        self.center = center
        self.image = frames[0]
        self.rect = self.image.get_rect(center=center)

    def update_effect(self, targets):
        self.tick()
        index = self.frame_number()
        if index >= len(self.frames):
            self.done = True
            return
        self.image = self.frames[index]
        self.rect = self.image.get_rect(center=self.center)


class Explosion(Effect):
    """A fighter blowing up (a Cell Jr. knocked out): sparks, then a big
    yellow blast growing and fading where it stood. Its frames: the hit
    sparks of Vegito's and the blasts of Gotenks' Buu's Fury sheets."""

    SPARKS = ("Graphics/assets/effects/vegito_fx.gif", (13, 107, 247),
              ((290, 298, 14, 15), (340, 294, 14, 15), (362, 294, 16, 16)))
    BLASTS = ("Graphics/assets/effects/gotenks_fx.gif", (13, 107, 247),
              ((199, 466, 32, 32), (250, 447, 32, 32), (330, 449, 32, 32), (370, 448, 32, 32)))
    FRAME_TICKS = 4
    _frames = None

    @classmethod
    def frames(cls):
        """Sparks then blasts, or [] when the sheets are missing."""
        if cls._frames is None:
            from animation import load_sheet
            frames = []
            try:
                for path, background, boxes in (cls.SPARKS, cls.BLASTS):
                    sheet = load_sheet(path)
                    for x, y, width, height in boxes:
                        frame = pygame.Surface((width, height))
                        frame.blit(sheet, (0, 0), (x, y, width, height))
                        frame.set_colorkey(background)
                        frames.append(frame)
            except (pygame.error, FileNotFoundError, OSError):
                frames = []
            cls._frames = frames
        return cls._frames

    def __init__(self, center, size=48):
        """center: where it blows up; size: the blast's width at its biggest."""
        super().__init__()
        self.center = center
        self.size = size
        if not self.frames():
            self.done = True
            return
        self.update_effect(())

    def update_effect(self, targets):
        self.tick()
        frames = self.frames()
        index = self.frame_number()
        if index >= len(frames) + 2:
            self.done = True
            return
        frame = frames[min(index, len(frames) - 1)]
        # It swells as it goes, and fades over its last frames
        growth = 0.6 + 0.6 * min(1.0, index / max(1, len(frames) - 1))
        side = max(8, round(self.size * growth * frame.get_width() / 32))
        self.image = pygame.transform.scale(frame, (side, round(side * frame.get_height() / frame.get_width())))
        self.image.set_colorkey(frame.get_colorkey())
        if index >= len(frames) - 1:
            self.image.set_alpha(max(0, 255 - 85 * (index - len(frames) + 2)))
        self.rect = self.image.get_rect(center=self.center)


def chest_origin(caster, direction):
    """Where an effect leaves the body: its edge, at chest height."""
    dx, dy = DIRECTION_VECTORS[direction]
    return (
        caster.rect.centerx + dx * caster.rect.width / 2,
        caster.rect.centery + 2 + dy * caster.rect.height / 2,
    )


def scale_frame(image, factor):
    """Pixel-art resize (nearest pixel), keeping the transparent colour."""
    if abs(factor - 1) < 0.01:
        return image
    size = (max(1, round(image.get_width() * factor)), max(1, round(image.get_height() * factor)))
    scaled = pygame.transform.scale(image, size)
    if image.get_colorkey() is not None:
        scaled.set_colorkey(image.get_colorkey())
    return scaled


def charge_scale(power):
    """Size of a charged technique: 0.7x at a tap, 1.2x fully charged."""
    return 0.7 + 0.5 * power


class Aura(Effect):
    """The Super Saiyan aura: golden flames around a fighter while it
    transforms (and a moment after, fading), drawn behind it.

    Its frames are the three aura flames of Vegeta's Buu's Fury sheet,
    sized to the fighter (bigger around Cell or Majin Buu)."""

    # The golden flames (Vegeta's sheet), and the auras of their own: Goku
    # Black's pink one (Super Saiyan Rosé)
    STYLES = {
        "gold": {"sheet": "Graphics/assets/effects/fusion_dance.png", "background": (0, 128, 0),
                 "boxes": ((321, 353, 32, 32), (360, 353, 32, 32), (397, 353, 32, 32)), "height": 1.35},
        "rose": {"sheet": "Graphics/assets/effects/goku_black_fx.png", "background": (87, 137, 170),
                 "boxes": ((437, 72, 96, 78), (547, 72, 96, 78), (657, 72, 96, 78)), "height": 1.5},
        # Super Saiyan Blue: the golden flames turned blue (red and blue swapped)
        "blue": {"sheet": "Graphics/assets/effects/fusion_dance.png", "background": (0, 128, 0),
                 "boxes": ((321, 353, 32, 32), (360, 353, 32, 32), (397, 353, 32, 32)), "height": 1.35,
                 "swap_red_blue": True},
    }
    CHARACTER_STYLES = {"goku_black": "rose"}
    FORM_STYLES = {"ssjb": "blue"}
    FRAME_TICKS = 5
    FADE_TICKS = 24
    layer = CHARACTER_LAYER
    _frames = {}

    @classmethod
    def frames(cls, style="gold"):
        """The flames of a style, or [] when its sheet is missing."""
        if style not in cls._frames:
            from animation import load_sheet
            info = cls.STYLES[style]
            try:
                sheet = load_sheet(info["sheet"])
            except (pygame.error, FileNotFoundError, OSError):
                cls._frames[style] = []
                return cls._frames[style]
            frames = []
            for x, y, width, height in info["boxes"]:
                frame = pygame.Surface((width, height))
                frame.blit(sheet, (0, 0), (x, y, width, height))
                if info.get("swap_red_blue"):
                    background = tuple(info["background"])
                    for px in range(width):
                        for py in range(height):
                            r, g, b = frame.get_at((px, py))[:3]
                            if (r, g, b) != background:
                                frame.set_at((px, py), (b, g, r))
                frame.set_colorkey(info["background"])
                frames.append(frame)
            cls._frames[style] = frames
        return cls._frames[style]

    def __init__(self, fighter, action="transform", at_least=50):
        """Around fighter while its action is action (and at_least ticks)."""
        super().__init__()
        self.fighter = fighter
        self.action = action
        self.at_least = at_least
        self.fading = 0.0
        self._offset = (0, 0)
        self.style = (self.FORM_STYLES.get(fighter.form) or self.CHARACTER_STYLES.get(fighter.character_name)
                      or "gold")
        if not self.frames(self.style):
            self.style = "gold"
        if not self.frames(self.style):
            self.done = True
            return
        self.update_effect(())

    @property
    def active(self):
        action = self.fighter.action
        doing = self.action is not None and action is not None and action["name"] == self.action
        return self.fighter.hp > 0 and (doing or self.ticks < self.at_least)

    def update_effect(self, targets):
        self.tick()
        if not self.active:
            self.fading += timing.ticks()
            if self.fading >= self.FADE_TICKS:
                self.done = True
                return
        frames = self.frames(self.style)
        frame = frames[self.frame_number() % len(frames)]
        body = drawn_rect(self.fighter)
        # Taller than the fighter, a little wider than tall: flames all round
        height = max(30, round(body.height * self.STYLES[self.style]["height"]))
        width = max(26, round(max(body.width * 1.3, height * frame.get_width() / frame.get_height() * 0.85)))
        self.image = pygame.transform.scale(frame, (width, height))
        self.image.set_colorkey(self.STYLES[self.style]["background"])
        if self.fading:
            self.image.set_alpha(round(255 * (1 - self.fading / self.FADE_TICKS)))
        drawn = self.image.get_rect(midbottom=(body.centerx, body.bottom + 3))
        # The map draws the lower sprite in front: the aura's own rect stands
        # a pixel above the fighter's feet (behind it), and image_offset puts
        # the picture back where it belongs
        self.rect = drawn.copy()
        self.rect.bottom = min(drawn.bottom, self.fighter.rect.bottom - 1)
        self._offset = (0, drawn.bottom - self.rect.bottom)

    def image_offset(self):
        return self._offset


class ChargeGlow(Effect):
    """The ki ball growing in the hands while a technique charges."""

    def __init__(self, frames, caster, scale=1.0):
        super().__init__()
        self.frames = frames
        self.caster = caster
        self.scale = scale
        self.level = 0.0
        self.update_effect(())

    def update_effect(self, targets):
        self.tick()
        index = min(len(self.frames) - 1, int(self.level * len(self.frames)))
        # A slight pulse so the charge looks alive
        pulse = 1 + 0.08 * (self.frame_number(3) % 2)
        self.image = scale_frame(self.frames[index], (0.8 + 0.4 * self.level) * pulse * self.scale)
        self.rect = self.image.get_rect(center=chest_origin(self.caster, self.caster.facing))


class Projectile(Effect):
    """An energy blast or ki ball flying straight until it hits."""

    def __init__(self, frames, hit_frames, origin, direction, speed, max_range, damage, on_hit,
                 grow_frames=(), spawn=None):
        super().__init__()
        self.frames = frames
        self.hit_frames = hit_frames
        self.grow_frames = list(grow_frames)
        self.center = list(origin)
        self.direction = DIRECTION_VECTORS[direction]
        self.speed = speed
        self.max_range = max_range
        self.travelled = 0
        self.damage = damage
        self.on_hit = on_hit
        self.spawn = spawn  # called with new effects (the spark)
        self._set_image(self.grow_frames[0] if self.grow_frames else frames[0])

    def _set_image(self, image):
        self.image = image
        self.rect = image.get_rect(center=(round(self.center[0]), round(self.center[1])))

    def update_effect(self, targets):
        self.tick()
        growing = self.frame_number()
        if growing < len(self.grow_frames):
            # A ki ball grows in the hands before it flies
            self._set_image(self.grow_frames[growing])
            return
        step = self.speed * timing.ticks()
        self.center[0] += self.direction[0] * step
        self.center[1] += self.direction[1] * step
        self.travelled += step
        index = self.frame_number() % len(self.frames)
        self._set_image(self.frames[index])
        for target in self._alive(targets):
            if effect_touches(self, target):
                if self.on_hit is not None:
                    self.on_hit(target, self.damage, tuple(self.center), 1.5)
                self._explode(target.rect.center)
                return
        if self.travelled >= self.max_range:
            self._explode(tuple(self.center))

    def _explode(self, center):
        self.done = True
        if self.spawn is not None and self.hit_frames:
            self.spawn(Spark(self.hit_frames, center))


class Beam(Effect):
    """A Kamehameha-style beam growing from the hands until it hits."""

    def __init__(self, pieces, origin, direction, speed, max_range, damage, on_hit, hold_ticks, orient):
        super().__init__()
        self.pieces = pieces  # {"start", "bodies", "heads", "impacts"}, facing right
        self.origin = origin
        self.direction_name = direction
        self.direction = DIRECTION_VECTORS[direction]
        self.speed = speed
        self.max_range = max_range
        self.damage = damage
        self.on_hit = on_hit
        self.hold_ticks = hold_ticks
        self.orient = orient
        self.length = 0
        self.hit = False
        self.stopped = False
        self._composed = None
        self._compose()

    def _compose(self):
        """Build the beam's picture; only when what it shows changed (it
        grows a few pixels a frame, and its head animates every few ticks):
        drawing, scaling and turning it is the costly part."""
        frame = self.frame_number()
        state = (int(self.length), self.hit, frame)
        if state == self._composed:
            return
        self._composed = state
        start = self.pieces.get("start")
        heads = self.pieces["impacts"] if self.hit and self.pieces.get("impacts") else self.pieces["heads"]
        head = heads[frame % len(heads)]
        bodies = self.pieces["bodies"]
        body = bodies[frame % len(bodies)]
        start_width = start.get_width() if start is not None else 0
        height = max(head.get_height(), body.get_height(), start.get_height() if start else 0)
        length = max(int(self.length), head.get_width() + start_width + 1)
        body_width = max(1, length - head.get_width() - start_width)
        image = pygame.Surface((length, height), pygame.SRCALPHA)
        x = 0
        if start is not None:
            image.blit(start, (0, (height - start.get_height()) // 2))
            x = start_width
        body_y = (height - body.get_height()) // 2
        if self.pieces.get("tile"):
            # A body drawn with its own detail (bolts of energy): repeated
            # along the beam, not stretched into streaks
            image.set_clip(pygame.Rect(x, 0, body_width, height))
            for tile_x in range(x, x + body_width, max(1, body.get_width())):
                image.blit(body, (tile_x, body_y))
            image.set_clip(None)
        else:
            image.blit(pygame.transform.scale(body, (body_width, body.get_height())), (x, body_y))
        image.blit(head, (x + body_width, (height - head.get_height()) // 2))
        self.image = self.orient(image, self.direction_name)
        # Anchor the beam's tail on the hands
        ox, oy = self.origin
        dx, dy = self.direction
        if dx > 0:
            self.rect = self.image.get_rect(midleft=(ox, oy))
        elif dx < 0:
            self.rect = self.image.get_rect(midright=(ox, oy))
        elif dy > 0:
            self.rect = self.image.get_rect(midtop=(ox, oy))
        else:
            self.rect = self.image.get_rect(midbottom=(ox, oy))

    def update_effect(self, targets):
        self.tick()
        if not self.stopped:
            self.length = min(self.max_range, self.length + self.speed * timing.ticks())
            self._compose()
            hits = [target for target in self._alive(targets) if effect_touches(self, target)]
            if hits:
                target = min(hits, key=lambda t: math.dist(self.origin, t.rect.center))
                if self.on_hit is not None:
                    self.on_hit(target, self.damage, self.origin, 2.0)
                self.hit = True
                self.stopped = True
                self.length = max(1, math.dist(self.origin, target.rect.center))
            elif self.length >= self.max_range:
                self.stopped = True
            self._compose()  # nothing to do unless it just hit
            return
        self.hold_ticks -= timing.ticks()
        self._compose()
        if self.hold_ticks <= 0:
            self.done = True


class Burst(Effect):
    """A shockwave growing around the caster, hitting everyone close."""

    HIT_FRAME = 3

    def __init__(self, frames, center, radius, damage, on_hit):
        super().__init__()
        self.frames = frames
        self.center = center
        self.radius = radius
        self.damage = damage
        self.on_hit = on_hit
        self.struck = False
        self.image = frames[0]
        self.rect = self.image.get_rect(center=center)

    def update_effect(self, targets):
        self.tick()
        index = self.frame_number()
        if index >= len(self.frames):
            self.done = True
            return
        # The rings are drawn twice their size on the sheet
        frame = self.frames[index]
        self.image = pygame.transform.scale(frame, (frame.get_width() * 2, frame.get_height() * 2))
        self.rect = self.image.get_rect(center=self.center)
        if index >= self.HIT_FRAME and not self.struck:
            self.struck = True
            for target in self._alive(targets):
                if math.dist(self.center, target.feet.center) <= self.radius:
                    if self.on_hit is not None:
                        self.on_hit(target, self.damage, self.center, 4.0)


def _rotate(image, direction):
    if direction == "Right":
        return image
    if direction == "Left":
        return pygame.transform.flip(image, True, False)
    return pygame.transform.rotate(image, 90 if direction == "Up" else -90)


def _region(image, x, width):
    """A vertical slice of a colour-keyed frame, still colour-keyed."""
    key = image.get_colorkey()
    piece = pygame.Surface((width, image.get_height()))
    if key is not None:
        piece.fill(key)
    piece.blit(image, (0, 0), (x, 0, width, image.get_height()))
    if key is not None:
        piece.set_colorkey(key)
    return piece


def beam_pieces(sprites):
    """Start, body, head (and impact head) of a beam, facing right."""
    cached = getattr(sprites, "_beam_pieces", None)
    if cached is not None:
        return cached
    data = sprites.data["beam"]
    if "full" in data:
        # Whole beams on the sheet: cut them into tail, body and head
        tail, head = data["tail"], data["head"]
        starts, bodies, heads = [], [], []
        for frame in [sprites.cut(box) for box in data["full"]]:
            width = frame.get_width()
            starts.append(_region(frame, 0, tail))
            bodies.append(_region(frame, tail, max(1, width - tail - head)))
            heads.append(_region(frame, width - head, head))
        pieces = {"start": starts[0], "bodies": bodies, "heads": heads, "impacts": None}
    else:
        flip = data.get("points_left", False)
        pieces = {
            "start": sprites.cut(data["start"], flip) if "start" in data else None,
            # One body, or several (animated)
            "bodies": [sprites.cut(box, flip) for box in data.get("bodies", [data.get("body")])],
            "heads": [sprites.cut(box, flip) for box in data["head"]],
            "impacts": [sprites.cut(box, flip) for box in data.get("impact", [])] or None,
            # Bodies repeated along the beam instead of stretched
            "tile": data.get("tile", False),
        }
    sprites._beam_pieces = pieces
    return pieces


def build_effect(technique, sprites, caster, direction, damage, on_hit, spawn, origin=None, power=None):
    """The effect of a technique leaving caster's hands towards direction.

    power (0 to 1): how much a chargeable technique was charged; it sets
    the size (and a beam's reach). None: not charged.
    """
    if sprites is None:
        return None
    stats = technique.stats
    kind = technique.kind
    if origin is None:
        origin = tuple(caster.rect.center) if kind == "burst" else chest_origin(caster, direction)
    origin = (float(origin[0]), float(origin[1]))
    scale = 1.0 if power is None else charge_scale(power)
    scale *= sprites.data.get("scale", 1.0)  # e.g. a bigger SSJ3 Kamehameha
    scale *= getattr(technique, "effect_scale", 1.0)  # a signature technique
    if kind in ("projectile", "ball"):
        frames = [scale_frame(sprites.oriented(image, direction), scale) for image in sprites.cuts("projectile")]
        if not frames:
            return None
        # A charged ball already grew in the hands
        grow = [scale_frame(f, scale) for f in sprites.cuts("grow")] if power is None else ()
        effect = Projectile(frames, [scale_frame(f, scale) for f in sprites.cuts("hit")], origin,
                            direction, stats["speed"], stats["range"], damage, on_hit,
                            grow_frames=grow, spawn=spawn)
    elif kind == "beam":
        pieces = beam_pieces(sprites)
        if scale != 1.0:
            pieces = {
                "start": scale_frame(pieces["start"], scale) if pieces["start"] is not None else None,
                "bodies": [scale_frame(piece, scale) for piece in pieces["bodies"]],
                "heads": [scale_frame(piece, scale) for piece in pieces["heads"]],
                "impacts": [scale_frame(piece, scale) for piece in pieces["impacts"]] if pieces["impacts"] else None,
                "tile": pieces.get("tile", False),
            }
        reach = stats["range"] * (1.0 if power is None else 0.6 + 0.4 * power)
        effect = Beam(pieces, origin, direction, stats["speed"], reach,
                      damage, on_hit, stats["hold_ticks"], _rotate)
    elif kind == "burst":
        frames = sprites.cuts("rings")
        if not frames:
            return None
        effect = Burst(frames, origin, stats["radius"], damage, on_hit)
    else:
        return None
    effect.origin_point = origin
    return effect


def effect_origin(effect, caster, direction):
    return [round(value, 2) for value in effect.origin_point]
