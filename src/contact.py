"""Whether two things really touch on screen: their drawn pixels overlap
(transparent pixels do not count). Hits only land on contact: a punch or a
kick when its extended frame reaches the target's body, a blast or a beam
when it reaches it (not just their rectangles, which have empty margins).
"""

import pygame

# Pixels of slack: a fist one or two pixels short of a body still lands
SLACK = 2

_masks = {}


def mask_of(image):
    """The image's mask (cached: frames are shared surfaces)."""
    key = id(image)
    cached = _masks.get(key)
    if cached is None or cached[0] is not image:
        if len(_masks) > 4096:
            _masks.clear()
        cached = _masks[key] = (image, pygame.mask.from_surface(image))
    return cached[1]


def drawn_rect(character, image=None):
    """Where character draws image (its current frame by default): frames
    of every size stand centred on the same feet (see image_offset)."""
    image = image or character.image
    rect = character.rect
    return pygame.Rect(rect.x + (rect.width - image.get_width()) // 2, rect.bottom - image.get_height(),
                       image.get_width(), image.get_height())


def touches(image_a, rect_a, image_b, rect_b, slack=SLACK):
    """Whether image_a drawn at rect_a and image_b at rect_b overlap (or
    come within slack pixels)."""
    if not rect_a.inflate(slack * 2, slack * 2).colliderect(rect_b):
        return False
    mask_a, mask_b = mask_of(image_a), mask_of(image_b)
    for dx, dy in ((0, 0), (slack, 0), (-slack, 0), (0, slack), (0, -slack)):
        if mask_a.overlap(mask_b, (rect_b.x - rect_a.x + dx, rect_b.y - rect_a.y + dy)) is not None:
            return True
    return False


def character_touches(attacker, target, image=None):
    """Whether attacker, showing image (its current frame by default),
    touches target as drawn. Bodies pressed against each other count too:
    fighters cannot overlap, and a short punch frame must still land."""
    if attacker.body.inflate(4, 4).colliderect(target.body):
        return True
    image = image or attacker.image
    return touches(image, drawn_rect(attacker, image), target.image, drawn_rect(target))


def reaching_frame(character):
    """The frame of its next punch that reaches out the most (to tell if a
    strike from here would land)."""
    moves = character.attack_moves(character.facing)
    if not moves:
        return character.image
    horizontal = character.facing in ("Left", "Right")
    return max(moves[character.attack_move_index % len(moves)],
               key=lambda frame: frame.get_width() if horizontal else frame.get_height())


def effect_touches(effect, target):
    """Whether a technique's effect (a sprite with image and rect) touches
    target as drawn."""
    return touches(effect.image, effect.rect, target.image, drawn_rect(target))
