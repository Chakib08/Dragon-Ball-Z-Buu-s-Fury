import pygame


def _feet_at(character, position):
    x, y = position
    width = character.feet.width
    height = character.feet.height
    x_offset = (character.rect.width - width) / 2
    y_offset = character.rect.height - height
    return pygame.Rect(x + x_offset, y + y_offset, width, height)


def _body_at(character, position):
    """The character's body (see Character.body) if it stood at position."""
    rect = character.rect.copy()
    rect.topleft = position  # rounded like Character.update rounds it
    body = pygame.Rect(0, 0, character.body_width, character.BODY_DEPTH)
    body.midbottom = rect.midbottom
    return body


def solid_bodies(characters, moving=None):
    """Bodies the moving character bumps into: the others still standing
    (a knocked-out character lies on the ground and can be walked over)."""
    return [c.body for c in characters if c is not moving and c.hp > 0]


def _body_overlap(body, bodies):
    """How far body is inside the others. Measured from the centres, so it
    keeps growing as two bodies get closer, even once a narrow body is all
    inside a wide one (an area would stop growing, and let it slip through)."""
    total = 0
    for other in bodies:
        overlap_x = (body.width + other.width) / 2 - abs(body.centerx - other.centerx)
        overlap_y = (body.height + other.height) / 2 - abs(body.centery - other.centery)
        if overlap_x > 0 and overlap_y > 0:
            total += overlap_x * overlap_y
    return total


def _overlap_area(rect, obstacles):
    """Total area of rect covered by the obstacles.

    collidelistall finds the few touching obstacles in C, instead of
    measuring every wall of the map in Python.
    """
    total = 0
    for index in rect.collidelistall(obstacles):
        overlap = rect.clip(obstacles[index])
        total += overlap.width * overlap.height
    return total


def resolve_movement_collisions(character, obstacles, bodies=()):
    """Undo the part of the last move (along x, then y) that pushed the
    character's feet into obstacles (walls) or its body into other bodies
    (characters). Moving out of an overlap is always allowed, so nobody
    gets stuck in a wall or in someone else."""
    def area(position):
        total = _overlap_area(_feet_at(character, position), obstacles)
        if bodies:
            total += _body_overlap(_body_at(character, position), bodies)
        return total

    old_x, old_y = character.old_position
    x, y = character.position
    current_area = area((old_x, old_y))

    x_area = area((x, old_y))
    if x_area <= current_area:
        old_x = x
        current_area = x_area
    else:
        x = old_x

    y_area = area((old_x, y))
    if y_area > current_area:
        y = old_y

    character.position = [x, y]
    character.update()
    character.save_location()
