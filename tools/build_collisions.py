#!/usr/bin/env python3
"""Generate the collision boxes of the maps (Graphics/maps/*.tmx).

Characters collide with their feet only, so for each room this describes
where feet may go: the floor ("walk" rectangles, in map pixels), minus the
furniture ("obstacles"). Everything else (walls, the void around the room)
is blocked. On the world map, the river is blocked wherever the map is
painted river-blue, except on the bridge, and a border keeps everyone on
the map.

The boxes are written into each map as collision objects named "auto_wall",
"auto_water" or "auto_border"; running this again replaces them and leaves
the hand-made collision objects alone.

    python3 tools/build_collisions.py            # rewrite the maps
    python3 tools/build_collisions.py --check    # only report
"""

import argparse
import os
import re
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP_DIR = os.path.join(ROOT, "Graphics", "maps")
CELL = 4  # map pixels per grid cell

# (x0, y0, x1, y1) in map pixels: floor where feet may go, and furniture
ROOMS = {
    "hall": {
        "walk": [
            (76, 234, 330, 260),    # corridor
            (250, 196, 330, 234),   # alcove by the stairs
            (276, 180, 304, 196),   # stairs (exit_hall)
            (130, 224, 152, 234),   # door to Gohan and Goten's room
            (130, 260, 160, 276),   # stairs down (enter_chichi_room)
        ],
        "obstacles": [
            (250, 214, 268, 234),   # lamp table
            (308, 220, 332, 236),   # plant
        ],
    },
    "kitchen": {
        "walk": [
            (89, 212, 272, 322),    # tiled floor
            (178, 322, 206, 336),   # doorway (exit_kitchen)
        ],
        "obstacles": [
            (89, 200, 112, 276),    # left counter
            (89, 276, 114, 302),    # pots, bottom left
            (254, 196, 272, 262),   # cabinet and television
            (254, 262, 272, 314),   # pots, right
            (162, 246, 206, 274),   # table
            (152, 268, 168, 284),   # left chair
            (208, 262, 224, 276),   # right chair
            (176, 226, 192, 240),   # chair behind the table
        ],
    },
    "chichi_room": {
        "walk": [
            (104, 223, 342, 287),   # bedroom
            (58, 244, 104, 287),    # alcove on the left
            (146, 208, 166, 224),   # door (exit_chichi_room)
        ],
        "obstacles": [
            (108, 222, 134, 234),   # plant
            (234, 222, 274, 248),   # bed
            (318, 222, 346, 236),   # dresser
            (72, 248, 92, 266),     # chest
            # Rounded corners at the bottom
            (58, 266, 70, 290), (70, 278, 90, 290),
            (330, 250, 346, 290), (316, 270, 330, 290), (302, 282, 316, 290),
        ],
    },
    "gohan_goten_room": {
        "walk": [
            (88, 242, 272, 312),    # bedroom
            (128, 312, 272, 344),   # lower part
            (176, 344, 204, 356),   # doorway (exit_gohan_goten_room)
        ],
        "obstacles": [
            (102, 236, 136, 260),   # toy box
            (142, 236, 208, 250),   # bed
            (246, 268, 272, 332),   # desk
            (232, 298, 248, 312),   # chair
        ],
    },
    "house": {
        # The furniture already has hand-made collision boxes in this map
        "walk": [
            (60, 248, 378, 368),    # living room
            (252, 168, 378, 248),   # upper part, by the stairs
            (300, 118, 332, 168),   # stairs (enter_hall)
            (150, 236, 168, 248),   # kitchen door (enter_kitchen)
            (202, 366, 234, 382),   # front door (exit_house)
        ],
        "obstacles": [
            # Rounded corners at the bottom
            (60, 340, 80, 370), (80, 356, 100, 370),
            (360, 340, 380, 370), (340, 356, 360, 370),
        ],
    },
}

# World map: river colours, and the bridge that crosses it
RIVER_COLOURS = {(88, 168, 248), (144, 200, 248)}
WORLD_CELL = 8
BRIDGE = (216, 396, 282, 552)


def merge_cells(blocked, columns, rows, cell):
    """Blocked grid cells -> as few rectangles as practical (row runs,
    then identical runs on consecutive rows merged)."""
    runs = {}
    for row in range(rows):
        column = 0
        while column < columns:
            if blocked[row][column]:
                start = column
                while column < columns and blocked[row][column]:
                    column += 1
                runs.setdefault((start, column), []).append(row)
            else:
                column += 1
    rects = []
    for (start, end), row_list in runs.items():
        top = previous = row_list[0]
        for row in row_list[1:] + [None]:
            if row is not None and row == previous + 1:
                previous = row
                continue
            rects.append((start * cell, top * cell, (end - start) * cell, (previous - top + 1) * cell))
            if row is not None:
                top = previous = row
    return sorted(rects, key=lambda r: (r[1], r[0]))


def inside(cell_rect, rect):
    """The cell's centre is in rect (so floor rectangles that meet between
    two grid lines join without a gap)."""
    x, y, w, h = cell_rect
    cx, cy = x + w / 2, y + h / 2
    return rect[0] <= cx < rect[2] and rect[1] <= cy < rect[3]


def overlaps(cell_rect, rect):
    x, y, w, h = cell_rect
    return x < rect[2] and rect[0] < x + w and y < rect[3] and rect[1] < y + h


def room_rects(size, room):
    columns, rows = size[0] // CELL, size[1] // CELL
    blocked = [[False] * columns for _ in range(rows)]
    for row in range(rows):
        for column in range(columns):
            cell = (column * CELL, row * CELL, CELL, CELL)
            walkable = any(inside(cell, rect) for rect in room["walk"])
            if not walkable or any(overlaps(cell, rect) for rect in room["obstacles"]):
                blocked[row][column] = True
    return merge_cells(blocked, columns, rows, CELL)


def world_rects(tmx_path, size):
    import pytmx
    pygame.init()
    pygame.display.set_mode((1, 1))
    data = pytmx.load_pygame(tmx_path)
    picture = pygame.Surface(size)
    for layer in data.visible_layers:
        if isinstance(layer, pytmx.TiledTileLayer):
            for x, y, image in layer.tiles():
                picture.blit(image, (x * data.tilewidth, y * data.tileheight))
    columns, rows = size[0] // WORLD_CELL, size[1] // WORLD_CELL
    blocked = [[False] * columns for _ in range(rows)]
    for row in range(rows):
        for column in range(columns):
            cell = (column * WORLD_CELL, row * WORLD_CELL, WORLD_CELL, WORLD_CELL)
            if overlaps(cell, BRIDGE):
                continue
            water = sum(
                1
                for dx in range(0, WORLD_CELL, 2)
                for dy in range(0, WORLD_CELL, 2)
                if tuple(picture.get_at((cell[0] + dx, cell[1] + dy)))[:3] in RIVER_COLOURS
            )
            blocked[row][column] = water * 2 >= (WORLD_CELL // 2) ** 2
    water = merge_cells(blocked, columns, rows, WORLD_CELL)
    border = [(-16, -16, size[0] + 32, 16), (-16, size[1], size[0] + 32, 16),
              (-16, 0, 16, size[1]), (size[0], 0, 16, size[1])]
    return [("auto_water", rect) for rect in water] + [("auto_border", rect) for rect in border]


def map_size(text):
    width = int(re.search(r'<map [^>]*\bwidth="(\d+)"', text).group(1))
    height = int(re.search(r'<map [^>]*\bheight="(\d+)"', text).group(1))
    tile_w = int(re.search(r'<map [^>]*\btilewidth="(\d+)"', text).group(1))
    tile_h = int(re.search(r'<map [^>]*\btileheight="(\d+)"', text).group(1))
    return width * tile_w, height * tile_h


AUTO_OBJECT = re.compile(r'\n *<object id="\d+" name="auto_(?:wall|water|border)"[^>]*/>')


def write_objects(text, named_rects):
    """Replace the generated collision objects in the map's Object layer."""
    text = AUTO_OBJECT.sub("", text)
    next_id = int(re.search(r'nextobjectid="(\d+)"', text).group(1))
    lines = []
    for name, (x, y, w, h) in named_rects:
        lines.append(f' <object id="{next_id}" name="{name}" type="collision" '
                     f'x="{x}" y="{y}" width="{w}" height="{h}"/>')
        next_id += 1
    match = re.search(r'(<objectgroup [^>]*name="Object"[^>]*>)(.*?)(\n *</objectgroup>)', text, re.S)
    if match is None:
        raise ValueError("no object layer named Object")
    body = match.group(2) + "".join("\n " + line for line in lines)
    text = text[:match.start(2)] + body + text[match.end(2):]
    return re.sub(r'nextobjectid="\d+"', f'nextobjectid="{next_id}"', text, count=1)


def build(name, check=False):
    path = os.path.join(MAP_DIR, f"{name}.tmx")
    with open(path) as file:
        text = file.read()
    size = map_size(text)
    if name == "map":
        named = world_rects(path, size)
    else:
        named = [("auto_wall", rect) for rect in room_rects(size, ROOMS[name])]
    if not check:
        with open(path, "w") as file:
            file.write(write_objects(text, named))
    return len(named)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only report, do not write")
    args = parser.parse_args()
    for name in ("map", *ROOMS):
        count = build(name, args.check)
        print(f"{name}: {count} generated collision boxes")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "src"))
    main()
