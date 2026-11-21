#!/usr/bin/env python3
"""Build the fighting arenas from the map pictures of dbz-assets.

setup.sh downloads the pictures to Graphics/assets/maps/ and runs this:
each arena of Config/arenas.json (an area of a picture, where characters
can and cannot walk) becomes a map in Graphics/assets/arenas/ (with
tools/png_to_map.py), with a thumbnail for the map screens. Like the
pictures, the maps stay out of the repository.

    python3 tools/build_arenas.py            # the missing ones
    python3 tools/build_arenas.py --force    # all of them again
"""

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import png_to_map  # noqa: E402

PICTURES = os.path.join(ROOT, "Graphics", "assets", "maps")
OUT = os.path.join(ROOT, "Graphics", "assets", "arenas")
# The rippers' mint background, in its shades: never walkable
MINT = [(71, 255, 187), (52, 188, 136), (46, 165, 121)]


def arenas():
    with open(os.path.join(ROOT, "Config", "arenas.json")) as file:
        return json.load(file)["arenas"]


def build(arena, force=False):
    """Returns "built", "kept" or "missing" (its picture is not there)."""
    picture = os.path.join(PICTURES, f"{arena['source']}.png")
    if not os.path.exists(picture):
        return "missing"
    target = os.path.join(OUT, f"{arena['id']}.tmx")
    if os.path.exists(target) and not force:
        return "kept"
    png_to_map.convert(
        picture, arena["id"], out_dir=OUT, force=True,
        crop=tuple(arena["crop"]) if arena.get("crop") else None,
        walk_areas=[tuple(area) for area in arena.get("walk", [])],
        block_colours=MINT + [tuple(colour) for colour in arena.get("block", [])],
        water=bool(arena.get("water")),
        thumbnail=os.path.join(OUT, f"{arena['id']}_thumb.png"),
    )
    return "built"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="build every arena again")
    args = parser.parse_args()
    results = {}
    for arena in arenas():
        if arena.get("builtin"):
            continue
        try:
            results[arena["id"]] = build(arena, args.force)
        except (OSError, ValueError) as error:
            results[arena["id"]] = f"failed: {error}"
    for name, result in results.items():
        print(f"{name}: {result}")
    if any(result.startswith("failed") for result in results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
