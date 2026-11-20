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
from utils import timing

EFFECT_LAYER = 2


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


class ChargeGlow(Effect):
    """The ki ball growing in the hands while a technique charges."""

    def __init__(self, frames, caster):
        super().__init__()
        self.frames = frames
        self.caster = caster
        self.level = 0.0
        self.update_effect(())

    def update_effect(self, targets):
        self.tick()
        index = min(len(self.frames) - 1, int(self.level * len(self.frames)))
        # A slight pulse so the charge looks alive
        pulse = 1 + 0.08 * (self.frame_number(3) % 2)
        self.image = scale_frame(self.frames[index], (0.8 + 0.4 * self.level) * pulse)
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
            if self.rect.colliderect(target.rect):
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
        image.blit(pygame.transform.scale(body, (body_width, body.get_height())),
                   (x, (height - body.get_height()) // 2))
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
            hits = [target for target in self._alive(targets) if self.rect.colliderect(target.rect)]
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
            "bodies": [sprites.cut(data["body"], flip)],
            "heads": [sprites.cut(box, flip) for box in data["head"]],
            "impacts": [sprites.cut(box, flip) for box in data.get("impact", [])] or None,
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
    if kind in ("projectile", "ball"):
        frames = [scale_frame(sprites.oriented(image, direction), scale) for image in sprites.cuts("projectile")]
        if not frames:
            return None
        # A charged ball already grew in the hands
        grow = sprites.cuts("grow") if power is None else ()
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
