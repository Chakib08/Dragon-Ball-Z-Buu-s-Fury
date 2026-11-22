#!/usr/bin/env python3
"""Turn a PNG picture of a map into a map the game can play on.

The picture (any size, drawn or taken from a game) becomes a Tiled map like
the game's own (Graphics/maps/*.tmx): 16 x 16 tiles, identical ones kept
once in a tileset, and an object layer with what the game needs:

    collision boxes    where feet cannot go (see below), and a border
    spawn_world        where the player starts (feet)
    spawn_rival        where the other player starts online (feet)
    vegeta_path_0..3   the enemies' patrol: four points with free ground
                       between them

Where characters cannot walk comes from one or more of these:

    --mask mask.png         a copy of the picture where you painted the
                            blocked places (any colour but white; transparent
                            and white are free): the most precise
    --block-colour R,G,B    places of that colour in the picture (repeat it
                            for several colours; --tolerance sets how close)
    --water                 blue water, found by its colour
    --walkable-colour R,G,B the opposite: only places of these colours are
                            free (grass, paths...), everything else blocked
    --walk-area X0,Y0,X1,Y1 only inside these rectangles (repeat it) can
                            characters walk: a stadium's ring, not its stands
    --block-area X0,Y0,X1,Y1 never walkable (repeat it): a house, a statue
    --free-area X0,Y0,X1,Y1  always walkable (repeat it): a bridge over water,
                            ground of an odd colour

--crop X,Y,W,H cuts one area out of a bigger picture (a rip holding a whole
location); --drop-seams removes the lines rippers draw between the screens
they stitched (rows and columns of their mint background colours);
--thumbnail writes a small picture of the map (map screens).

A grid cell (--cell pixels) is blocked when at least --threshold of it is.
Check the result with --preview: the picture with the blocked places in red,
the spawn in green and the patrol in yellow.

Examples
    python3 tools/png_to_map.py arena.png arena --water --preview arena_check.png
    python3 tools/png_to_map.py arena.png arena --mask arena_mask.png
    python3 tools/png_to_map.py arena.png arena --walkable-colour 104,176,72 --walkable-colour 216,184,128

Then fight on it: set "arena": "arena" in Config/config.json (the map is
written to Graphics/maps/arena.tmx, with arena.tsx and arena_tiles.png).
"""

import argparse
import math
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
from build_collisions import merge_cells  # noqa: E402

MAP_DIR = os.path.join(ROOT, "Graphics", "maps")
TILESET_COLUMNS = 32
# Room a character needs around a spawn or patrol point, in pixels
FREE_RADIUS = 12
# The NPC sprites the patrol points are placed for (see NPC.position_at)
MAP_SPRITE_SIZE = 32


def parse_colour(text):
    try:
        parts = [int(part) for part in text.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r}: a colour is R,G,B (0-255)")
    if len(parts) != 3 or not all(0 <= part <= 255 for part in parts):
        raise argparse.ArgumentTypeError(f"{text!r}: a colour is R,G,B (0-255)")
    return tuple(parts)


def parse_box(text):
    try:
        parts = [int(part) for part in text.split(",")]
    except ValueError:
        parts = []
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(f"{text!r}: four numbers separated by commas")
    return tuple(parts)


SEAM_COLOURS = {(71, 255, 187), (52, 188, 136), (46, 165, 121)}


def seam_lines(picture):
    """(columns, rows) of the picture that are seam lines: at least 90% of
    their pixels in the rippers' mint colours."""
    width, height = picture.get_size()

    def is_seam(pixels):
        return sum(1 for colour in pixels if tuple(colour)[:3] in SEAM_COLOURS) >= 0.9 * len(pixels)

    step = 2
    columns = [x for x in range(width) if is_seam([picture.get_at((x, y)) for y in range(0, height, step)])]
    rows = [y for y in range(height) if is_seam([picture.get_at((x, y)) for x in range(0, width, step)])]
    return columns, rows


def without_lines(picture, columns, rows):
    """The picture with those columns and rows taken out."""
    keep_x = [x for x in range(picture.get_width()) if x not in set(columns)]
    keep_y = [y for y in range(picture.get_height()) if y not in set(rows)]
    narrow = pygame.Surface((len(keep_x), picture.get_height()), pygame.SRCALPHA)
    for new, old in enumerate(keep_x):
        narrow.blit(picture, (new, 0), (old, 0, 1, picture.get_height()))
    result = pygame.Surface((len(keep_x), len(keep_y)), pygame.SRCALPHA)
    for new, old in enumerate(keep_y):
        result.blit(narrow, (0, new), (0, old, len(keep_x), 1))
    return result


def parse_point(text):
    try:
        x, y = (int(part) for part in text.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r}: a point is X,Y (map pixels)")
    return x, y


# ---- Tiles ------------------------------------------------------------------------
def padded(picture, tile):
    """The picture grown to whole tiles (its edge colour fills the rest)."""
    width = -(-picture.get_width() // tile) * tile
    height = -(-picture.get_height() // tile) * tile
    if (width, height) == picture.get_size():
        return picture
    grown = pygame.Surface((width, height), pygame.SRCALPHA)
    grown.fill(picture.get_at((picture.get_width() - 1, picture.get_height() - 1)))
    grown.blit(picture, (0, 0))
    return grown


def cut_tiles(picture, tile):
    """(unique tiles, grid of tile numbers from 0) of the picture."""
    columns, rows = picture.get_width() // tile, picture.get_height() // tile
    unique, index, grid = [], {}, []
    for row in range(rows):
        line = []
        for column in range(columns):
            piece = picture.subsurface((column * tile, row * tile, tile, tile))
            key = pygame.image.tostring(piece, "RGBA")
            if key not in index:
                index[key] = len(unique)
                unique.append(piece.copy())
            line.append(index[key])
        grid.append(line)
    return unique, grid


def tileset_image(tiles, tile):
    columns = min(TILESET_COLUMNS, len(tiles))
    rows = -(-len(tiles) // columns)
    image = pygame.Surface((columns * tile, rows * tile), pygame.SRCALPHA)
    for number, piece in enumerate(tiles):
        image.blit(piece, ((number % columns) * tile, (number // columns) * tile))
    return image, columns


# ---- Where feet may go ------------------------------------------------------------------
def blocked_pixels(picture, mask=None, block_colours=(), walkable_colours=(), water=False, tolerance=24,
                   walk_areas=(), block_areas=(), free_areas=()):
    """A function telling if the pixel at (x, y) is blocked. walk_areas:
    (x0, y0, x1, y1) rectangles, in the map's pixels, outside which
    everything is blocked."""
    limit = tolerance * tolerance

    def near(colour, colours):
        return any((colour[0] - c[0]) ** 2 + (colour[1] - c[1]) ** 2 + (colour[2] - c[2]) ** 2 <= limit
                   for c in colours)

    def inside(x, y, areas):
        return any(x0 <= x < x1 and y0 <= y < y1 for x0, y0, x1, y1 in areas)

    def is_blocked(x, y):
        if walk_areas and not inside(x, y, walk_areas):
            return True
        if inside(x, y, block_areas):
            return True
        if inside(x, y, free_areas):
            return False
        if mask is not None:
            if x < mask.get_width() and y < mask.get_height():
                r, g, b, a = mask.get_at((x, y))
                if a > 0 and (r, g, b) != (255, 255, 255) and min(r, g, b) < 245:
                    return True
        if not (block_colours or walkable_colours or water):
            return False
        r, g, b, _ = picture.get_at((x, y))
        colour = (r, g, b)
        if block_colours and near(colour, block_colours):
            return True
        if water and b > r + 40 and b > g + 10 and b > 120:
            return True
        if walkable_colours and not near(colour, walkable_colours):
            return True
        return False

    return is_blocked


def blocked_grid(size, is_blocked, cell, threshold):
    columns, rows = size[0] // cell, size[1] // cell
    step = max(1, cell // 4)
    samples = [(dx, dy) for dx in range(step // 2, cell, step) for dy in range(step // 2, cell, step)]
    grid = []
    for row in range(rows):
        line = []
        for column in range(columns):
            hits = sum(1 for dx, dy in samples if is_blocked(column * cell + dx, row * cell + dy))
            line.append(hits >= threshold * len(samples))
        grid.append(line)
    return grid


def is_free(grid, cell, x, y, radius=FREE_RADIUS):
    """Room for a character's feet around (x, y)."""
    rows, columns = len(grid), len(grid[0]) if grid else 0
    for dy in range(-radius, radius + 1, max(1, cell // 2)):
        for dx in range(-radius, radius + 1, max(1, cell // 2)):
            column, row = int((x + dx) // cell), int((y + dy) // cell)
            if not (0 <= row < rows and 0 <= column < columns) or grid[row][column]:
                return False
    return True


def nearest_free(grid, cell, x, y, size):
    """The free spot closest to (x, y), or None on a fully blocked map."""
    for radius in range(0, max(size), cell):
        for angle in range(0, 360, 15 if radius else 360):
            px = x + radius * math.cos(math.radians(angle))
            py = y + radius * math.sin(math.radians(angle))
            if 0 <= px < size[0] and 0 <= py < size[1] and is_free(grid, cell, px, py):
                return round(px), round(py)
    return None


def line_is_free(grid, cell, a, b):
    steps = max(1, int(math.dist(a, b) // (cell / 2)))
    return all(is_free(grid, cell, a[0] + (b[0] - a[0]) * i / steps, a[1] + (b[1] - a[1]) * i / steps, 6)
               for i in range(steps + 1))


def patrol_points(grid, cell, size, centre):
    """Four free points around centre, walkable from one to the next (the
    enemies walk straight between them); smaller squares if needed."""
    for radius in (min(size) * 0.18, min(size) * 0.12, min(size) * 0.07, 24):
        for turn in range(0, 90, 15):
            points = []
            for corner in range(4):
                angle = math.radians(turn + corner * 90 + 45)
                points.append(nearest_free(grid, cell, centre[0] + radius * math.cos(angle),
                                           centre[1] + radius * math.sin(angle), size))
            if None in points:
                continue
            if all(line_is_free(grid, cell, points[i], points[(i + 1) % 4]) for i in range(4)):
                return points
    spot = nearest_free(grid, cell, *centre, size)
    return [spot] * 4 if spot else None


# ---- Writing -------------------------------------------------------------------------------
def tmx_text(name, size_tiles, tile, grid, objects, next_id):
    columns, rows = size_tiles
    csv = ",\n".join(",".join(str(number + 1) for number in line) for line in grid)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<map version="1.10" tiledversion="1.10.1" orientation="orthogonal" renderorder="right-down" '
        f'width="{columns}" height="{rows}" tilewidth="{tile}" tileheight="{tile}" infinite="0" '
        f'nextlayerid="3" nextobjectid="{next_id}">',
        f' <tileset firstgid="1" source="{name}.tsx"/>',
        f' <layer id="1" name="Tile Layer 1" width="{columns}" height="{rows}">',
        '  <data encoding="csv">',
        csv,
        '</data>',
        ' </layer>',
        ' <objectgroup id="2" name="Object">',
        *objects,
        ' </objectgroup>',
        '</map>',
        '',
    ]
    return "\n".join(lines)


def tsx_text(name, tile, count, columns, image_size):
    return "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<tileset version="1.10" tiledversion="1.10.1" name="{name}" tilewidth="{tile}" tileheight="{tile}" '
        f'tilecount="{count}" columns="{columns}">',
        f' <image source="{name}_tiles.png" width="{image_size[0]}" height="{image_size[1]}"/>',
        '</tileset>',
        '',
    ])


def save_preview(path, picture, collisions, spawn, patrol):
    preview = picture.copy()
    shade = pygame.Surface(preview.get_size(), pygame.SRCALPHA)
    for x, y, w, h in collisions:
        pygame.draw.rect(shade, (230, 30, 30, 120), (x, y, w, h))
    preview.blit(shade, (0, 0))
    if patrol:
        pygame.draw.lines(preview, (255, 220, 40), True, patrol, 2)
        for point in patrol:
            pygame.draw.circle(preview, (255, 220, 40), point, 5)
    pygame.draw.circle(preview, (40, 230, 60), spawn, 7)
    pygame.image.save(preview, path)


def convert(picture_path, name, out_dir=MAP_DIR, tile=16, cell=8, threshold=0.5, mask_path=None,
            block_colours=(), walkable_colours=(), water=False, tolerance=24, spawn=None,
            preview=None, force=False, crop=None, walk_areas=(), thumbnail=None, thumbnail_size=(240, 160),
            block_areas=(), free_areas=(), patrol_centre=None, drop_seams=False):
    """Write <out_dir>/<name>.tmx, .tsx and _tiles.png; returns a summary."""
    if not name.replace("_", "").replace("-", "").isalnum():
        raise ValueError(f"{name!r}: use letters, digits, - and _ for the map's name")
    tmx_path = os.path.join(out_dir, f"{name}.tmx")
    if os.path.exists(tmx_path) and not force:
        raise FileExistsError(f"{tmx_path} exists (use --force to replace it)")
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    original = pygame.image.load(picture_path).convert_alpha()
    if crop:
        # One area of a bigger picture; the walk areas are given in the
        # big picture's pixels too
        x, y, w, h = crop
        original = original.subsurface(pygame.Rect(x, y, w, h).clip(original.get_rect())).copy()
        shift = lambda areas: [(x0 - x, y0 - y, x1 - x, y1 - y) for x0, y0, x1, y1 in areas]
        walk_areas, block_areas, free_areas = shift(walk_areas), shift(block_areas), shift(free_areas)
    if drop_seams:
        columns, rows = seam_lines(original)
        if columns or rows:
            original = without_lines(original, columns, rows)
            # What was given on the picture moves with the lines taken out
            fix_x = lambda value: value - sum(1 for column in columns if column < value)
            fix_y = lambda value: value - sum(1 for row in rows if row < value)
            fix = lambda areas: [(fix_x(x0), fix_y(y0), fix_x(x1), fix_y(y1)) for x0, y0, x1, y1 in areas]
            walk_areas, block_areas, free_areas = fix(walk_areas), fix(block_areas), fix(free_areas)
            spawn = (fix_x(spawn[0]), fix_y(spawn[1])) if spawn else None
            patrol_centre = (fix_x(patrol_centre[0]), fix_y(patrol_centre[1])) if patrol_centre else None
    picture = padded(original, tile)
    size = picture.get_size()
    mask = pygame.image.load(mask_path).convert_alpha() if mask_path else None
    if mask is not None and crop:
        mask = mask.subsurface(pygame.Rect(crop).clip(mask.get_rect())).copy()

    tiles, grid = cut_tiles(picture, tile)
    sheet, columns = tileset_image(tiles, tile)

    is_blocked = blocked_pixels(picture, mask, block_colours, walkable_colours, water, tolerance, walk_areas,
                                block_areas, free_areas)
    blocked = blocked_grid(size, is_blocked, cell, threshold)
    collisions = merge_cells(blocked, size[0] // cell, size[1] // cell, cell)
    border = [(-16, -16, size[0] + 32, 16), (-16, size[1], size[0] + 32, 16),
              (-16, 0, 16, size[1]), (size[0], 0, 16, size[1])]

    # The player on the left, the enemies' patrol towards the right
    wanted = spawn or (size[0] // 3, size[1] // 2)
    start = nearest_free(blocked, cell, wanted[0], wanted[1], size)
    if start is None:
        raise ValueError("nowhere to stand: the whole map is blocked (check the mask or colours)")
    centre = patrol_centre or (size[0] * 2 // 3, size[1] // 2)
    patrol = patrol_points(blocked, cell, size, centre) or [start] * 4
    # The other player online: across from the player
    rival = nearest_free(blocked, cell, size[0] * 2 // 3, wanted[1], size) or start

    objects, next_id = [], 1
    for rect_name, rects in (("auto_wall", collisions), ("auto_border", border)):
        for x, y, w, h in rects:
            objects.append(f'  <object id="{next_id}" name="{rect_name}" type="collision" '
                           f'x="{x}" y="{y}" width="{w}" height="{h}"/>')
            next_id += 1
    objects.append(f'  <object id="{next_id}" name="spawn_world" x="{start[0]}" y="{start[1]}">\n'
                   '   <point/>\n  </object>')
    next_id += 1
    objects.append(f'  <object id="{next_id}" name="spawn_rival" x="{rival[0]}" y="{rival[1]}">\n'
                   '   <point/>\n  </object>')
    next_id += 1
    for index, (x, y) in enumerate(patrol):
        # Top-left of a 32 px sprite whose feet stand on the point
        objects.append(f'  <object id="{next_id}" name="vegeta_path_{index}" '
                       f'x="{x - MAP_SPRITE_SIZE // 2}" y="{y - MAP_SPRITE_SIZE}" width="16" height="16"/>')
        next_id += 1

    os.makedirs(out_dir, exist_ok=True)
    pygame.image.save(sheet, os.path.join(out_dir, f"{name}_tiles.png"))
    with open(os.path.join(out_dir, f"{name}.tsx"), "w", encoding="utf-8") as file:
        file.write(tsx_text(name, tile, len(tiles), columns, sheet.get_size()))
    with open(tmx_path, "w", encoding="utf-8") as file:
        file.write(tmx_text(name, (size[0] // tile, size[1] // tile), tile, grid, objects, next_id))
    if preview:
        save_preview(preview, picture, collisions, start, patrol)
    if thumbnail:
        ratio = min(thumbnail_size[0] / size[0], thumbnail_size[1] / size[1])
        small = pygame.transform.smoothscale(picture.convert(), (max(1, round(size[0] * ratio)),
                                                                 max(1, round(size[1] * ratio))))
        pygame.image.save(small, thumbnail)
    return {"map": tmx_path, "size": size, "tiles": len(tiles), "collisions": len(collisions),
            "spawn": start, "patrol": patrol}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("picture", help="the PNG picture of the map")
    parser.add_argument("name", help="the map's name (Graphics/maps/<name>.tmx)")
    parser.add_argument("--mask", help="PNG where the blocked places are painted (white or transparent: free)")
    parser.add_argument("--block-colour", type=parse_colour, action="append", default=[], metavar="R,G,B")
    parser.add_argument("--walkable-colour", type=parse_colour, action="append", default=[], metavar="R,G,B")
    parser.add_argument("--water", action="store_true", help="block blue water")
    parser.add_argument("--walk-area", type=parse_box, action="append", default=[], metavar="X0,Y0,X1,Y1",
                        help="only inside these rectangles can characters walk")
    parser.add_argument("--block-area", type=parse_box, action="append", default=[], metavar="X0,Y0,X1,Y1",
                        help="never walkable")
    parser.add_argument("--free-area", type=parse_box, action="append", default=[], metavar="X0,Y0,X1,Y1",
                        help="always walkable")
    parser.add_argument("--crop", type=parse_box, metavar="X,Y,W,H", help="use only this area of the picture")
    parser.add_argument("--thumbnail", help="also save a small picture of the map")
    parser.add_argument("--tolerance", type=int, default=24, help="how close a colour must be (default 24)")
    parser.add_argument("--cell", type=int, default=8, help="collision grid, in pixels (default 8)")
    parser.add_argument("--threshold", type=float, default=0.5,
                        help="share of a cell that must be blocked to block it (default 0.5)")
    parser.add_argument("--tile", type=int, default=16, help="tile size (default 16, like the game's maps)")
    parser.add_argument("--spawn", type=parse_point, metavar="X,Y", help="where the player starts")
    parser.add_argument("--out-dir", default=MAP_DIR, help="where to write the map (default Graphics/maps)")
    parser.add_argument("--preview", help="also save this PNG: the collisions in red, the spawn and patrol")
    parser.add_argument("--force", action="store_true", help="replace a map of that name")
    args = parser.parse_args()
    try:
        summary = convert(args.picture, args.name, args.out_dir, args.tile, args.cell, args.threshold,
                          args.mask, args.block_colour, args.walkable_colour, args.water, args.tolerance,
                          args.spawn, args.preview, args.force, args.crop, args.walk_area, args.thumbnail,
                          block_areas=args.block_area, free_areas=args.free_area)
    except (OSError, ValueError, pygame.error) as error:
        sys.exit(f"error: {error}")
    print(f"{summary['map']}: {summary['size'][0]}x{summary['size'][1]} px, {summary['tiles']} unique tiles, "
          f"{summary['collisions']} collision boxes, spawn at {summary['spawn']}")
    print(f'Fight on it: set "arena": "{args.name}" in Config/config.json')


if __name__ == "__main__":
    main()
