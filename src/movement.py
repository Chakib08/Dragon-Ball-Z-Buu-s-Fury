import pygame


def _feet_at(character, position):
    x, y = position
    width = character.feet.width
    height = character.feet.height
    x_offset = (character.rect.width - width) / 2
    y_offset = character.rect.height - height
    return pygame.Rect(x + x_offset, y + y_offset, width, height)


def _overlap_area(rect, obstacles):
    return sum(
        max(0, min(rect.right, obstacle.right) - max(rect.left, obstacle.left))
        * max(0, min(rect.bottom, obstacle.bottom) - max(rect.top, obstacle.top))
        for obstacle in obstacles
    )


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
