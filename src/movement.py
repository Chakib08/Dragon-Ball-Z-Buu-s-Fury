import pygame


def _feet_at(character, position):
    x, y = position
    width = character.feet.width
    height = character.feet.height
    x_offset = (character.rect.width - width) / 2
    y_offset = character.rect.height - height
    return pygame.Rect(x + x_offset, y + y_offset, width, height)


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


def resolve_movement_collisions(character, obstacles):
    old_x, old_y = character.old_position
    x, y = character.position
    current_area = _overlap_area(_feet_at(character, (old_x, old_y)), obstacles)

    x_area = _overlap_area(_feet_at(character, (x, old_y)), obstacles)
    if x_area <= current_area:
        old_x = x
        current_area = x_area
    else:
        x = old_x

    y_area = _overlap_area(_feet_at(character, (old_x, y)), obstacles)
    if y_area > current_area:
        y = old_y

    character.position = [x, y]
    character.update()
    character.save_location()
