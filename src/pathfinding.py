"""Paths around walls, for the NPCs (see npc_ai.py).

The map is seen as a grid of GRID_SIZE pixel cells; a cell is walkable when
a character's feet, centred on it, touch no wall. find_path runs an A*
search from the character's cell to the first cell from where its target is
within reach, and returns the cells to walk through.
"""

import heapq
import math

import pygame

GRID_SIZE = 8
# Room around the walls and the two ends the search may use, in cells
MARGIN_CELLS = 2


def grid_cell(point):
    return round(point[0] / GRID_SIZE), round(point[1] / GRID_SIZE)


def cell_center(cell):
    """Where a character's feet are centred when it stands on cell."""
    return cell[0] * GRID_SIZE, cell[1] * GRID_SIZE


def feet_on_cell(character, cell):
    """character's feet rectangle when they are centred on cell."""
    center_x, center_y = cell_center(cell)
    width, height = character.feet.width, character.feet.height
    return pygame.Rect(center_x - width / 2, center_y - height / 2, width, height)


def walkable(character, cell, collisions):
    # collidelist tests every wall in C: a search visits thousands of cells
    return feet_on_cell(character, cell).collidelist(collisions) == -1


def search_bounds(start, target, collisions):
    """The cells the search may visit: around the walls and both ends (an
    open map has no edge of its own)."""
    points_x = [start[0], target[0]]
    points_y = [start[1], target[1]]
    for obstacle in collisions:
        points_x.extend((obstacle.left, obstacle.right))
        points_y.extend((obstacle.top, obstacle.bottom))
    return (
        math.floor(min(points_x) / GRID_SIZE) - MARGIN_CELLS,
        math.floor(max(points_x) / GRID_SIZE) + MARGIN_CELLS,
        math.floor(min(points_y) / GRID_SIZE) - MARGIN_CELLS,
        math.floor(max(points_y) / GRID_SIZE) + MARGIN_CELLS,
    )


def _in_bounds(cell, bounds):
    min_x, max_x, min_y, max_y = bounds
    return min_x <= cell[0] <= max_x and min_y <= cell[1] <= max_y


def find_path(character, target, collisions, reach):
    """Cells leading character's feet to within reach pixels of target (a
    point), the start excluded; [] when there is no way (or it is there)."""
    start = grid_cell(character.feet.center)
    target_cell = grid_cell(target)
    bounds = search_bounds(character.feet.center, target, collisions)
    frontier = [(0, start)]
    came_from = {start: None}
    cost_so_far = {start: 0}
    goal = None

    while frontier:
        _, current = heapq.heappop(frontier)
        if math.dist(cell_center(current), target) <= reach:
            goal = current
            break

        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            neighbor = (current[0] + dx, current[1] + dy)
            if not _in_bounds(neighbor, bounds) or not walkable(character, neighbor, collisions):
                continue
            new_cost = cost_so_far[current] + 1
            if neighbor in cost_so_far and new_cost >= cost_so_far[neighbor]:
                continue
            cost_so_far[neighbor] = new_cost
            heuristic = abs(neighbor[0] - target_cell[0]) + abs(neighbor[1] - target_cell[1])
            heapq.heappush(frontier, (new_cost + heuristic, neighbor))
            came_from[neighbor] = current

    if goal is None:
        return []
    path = []
    current = goal
    while current != start:
        path.append(current)
        current = came_from[current]
    path.reverse()
    return path
