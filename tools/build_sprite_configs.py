#!/usr/bin/env python3
"""Generate the sprite configs of the sheets from the dbz-assets repository.

The character sheets (downloaded by setup.sh) are grids of square cells, one
row per direction (Down, Left, Right, Up). Most use 32x32 cells from y=32
and the same columns for the moves every character has:

    0 idle, 2-5 walk, 6-9 run, 10-17 punches and kicks

The rest (hurt, guard, knock-out, transformation, technique poses) differs
per character and is listed in SHEETS below, with the layout of the sheets
that differ (Broly: 64x64 cells, no run).

Writes Config/characters/<name>/<form>.json, and in specials.json the
technique poses of those forms. The effects of the techniques (blasts,
beams, impacts...) come from the spritedatabase.net sheets kept in
Graphics/assets/effects/, or, for the characters that have none there
(Trunks, Broly), from the effects sheet of dbz-assets (EFFECTS_SHEET).

    python3 tools/build_sprite_configs.py
"""

import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRECTIONS = ("Down", "Right", "Left", "Up")
# The game mirrors the right-facing frames for the left
SOURCE_ROW = {"Down": "Down", "Right": "Right", "Left": "Right", "Up": "Up"}

# Layout of most sheets
CELL = 32
ROWS = {"Down": 32, "Left": 64, "Right": 96, "Up": 128}
WALK = [2, 3, 4, 5]
RUN = [6, 7, 8, 9]
# Four moves of three frames: punch, hook, knee and kick, second kick
ATTACK = [10, 11, 11, 12, 12, 13, 14, 15, 15, 16, 16, 17]

EFFECTS = "Graphics/assets/effects"
# Effects sheet of dbz-assets: frames on cells of two shades ("auto"
# background: the colour of each frame's own cell)
EFFECTS_SHEET = f"{EFFECTS}/sfx.png"

# Technique poses on each sheet: columns for all directions, or per
# direction; "row" takes them all from one row (poses drawn facing front)
GOKU_SSJ3_TECHNIQUES = {
    "energy_blast": {"pose": [24, 25, 26], "fire_at": 1},
    "kamehameha": {
        "pose": {"Down": [18, 20, 19], "Right": [18, 18, 18, 18, 20, 19], "Up": [18, 20, 19]},
        "fire_at": {"Right": 4, "Down": 1, "Up": 1},
    },
    "instant_transmission": {"vanish": [21, 22, 23]},
}
GOHAN_TECHNIQUES = {
    "energy_blast": {"pose": [24, 25, 26], "fire_at": 1},
    "kamehameha": {"pose": [18, 19, 20], "fire_at": 2},
    "ki_burst": {"pose": [31]},
}
VEGETA_TECHNIQUES = {
    "energy_blast": {"pose": [25, 26, 27], "fire_at": 1},
    "final_flash": {"pose": [21, 21, 24, 24], "fire_at": 2},
    "big_bang": {"pose": {"Down": [19, 19], "Right": [19, 19], "Up": [18, 19]}, "fire_at": 1},
}
TRUNKS_TECHNIQUES = {
    "energy_blast": {"pose": [29, 30, 31], "fire_at": 1},
    "burning_attack": {"pose": [29, 30, 30], "fire_at": 1},
    "sword_slash": {"pose": [32, 33, 34, 35], "fire_at": 1},
}
BROLY_TECHNIQUES = {
    "energy_blast": {"pose": [14, 15, 15], "fire_at": 1},
    "eraser_cannon": {"pose": [40, 41, 41], "row": "Down", "fire_at": 1},
    "blaster_shell": {"pose": [42, 43, 44, 45, 46], "row": "Down", "fire_at": 1},
}

SHEETS = [
    {
        "character": "goku", "form": "ssj3",
        "hurt": [28, 29], "block": 27, "special": [24, 25, 26],
        # The aura of the SSJ3 transformation is only on the old sheet
        "transform_old": {
            "sheet": f"{EFFECTS}/goku_ssj3.png", "background": (0, 128, 0),
            "boxes": [[10, 458, 32, 33], [49, 458, 32, 33], [86, 458, 32, 33], [126, 458, 32, 34],
                      [166, 458, 32, 34], [204, 458, 32, 34], [250, 458, 32, 34], [292, 458, 32, 34],
                      [338, 458, 32, 34], [381, 458, 32, 34], [423, 458, 32, 34], [466, 458, 32, 34],
                      [513, 458, 32, 33], [550, 458, 32, 33], [587, 458, 32, 33]],
        },
        "techniques": GOKU_SSJ3_TECHNIQUES,
        "effects": {"sheet": f"{EFFECTS}/goku_ssj3.png", "from_form": "ssj3"},
    },
    {
        "character": "gohan", "form": "base",
        "hurt": [28, 29], "block": 27, "special": [24, 25, 26],
        "faint": [44, 45, 46, 47], "transform": [63, 63, 64, 64, 65, 66, 65, 66, 67],
        "techniques": GOHAN_TECHNIQUES,
        "effects": {"sheet": f"{EFFECTS}/gohan_base.png", "from_form": "base"},
    },
    {
        "character": "gohan", "form": "ssj",
        "hurt": [28, 29], "block": 27, "special": [24, 25, 26],
        "techniques": GOHAN_TECHNIQUES,
        "effects": {"sheet": f"{EFFECTS}/gohan_base.png", "from_form": "base"},
    },
    {
        "character": "vegeta", "form": "base",
        "hurt": [29, 30], "block": 28, "special": [25, 26, 27],
        "faint": [45, 46, 47, 48], "transform": [52, 52, 53, 54, 53, 54, 55],
        "techniques": VEGETA_TECHNIQUES,
        "effects": {"sheet": f"{EFFECTS}/vegeta_ssj.png", "from_form": "ssj"},
    },
    {
        "character": "vegeta", "form": "ssj",
        "hurt": [29, 30], "block": 28, "special": [25, 26, 27],
        "techniques": VEGETA_TECHNIQUES,
        "effects": {"sheet": f"{EFFECTS}/vegeta_ssj.png", "from_form": "ssj"},
    },
    {
        "character": "trunks", "form": "base",
        "hurt": [36, 41], "block": 38, "special": [29, 30, 31],
        "faint": [52, 53, 54, 55], "transform": [58, 58, 59, 60, 61, 60, 61],
        "techniques": TRUNKS_TECHNIQUES,
    },
    {
        "character": "trunks", "form": "ssj",
        "hurt": [36, 41], "block": 38, "special": [29, 30, 31],
        "techniques": TRUNKS_TECHNIQUES,
    },
    {
        # Already the Legendary Super Saiyan: one form, bigger cells, and no
        # run (he walks faster instead); knocked out facing front
        "character": "broly", "form": "base",
        "cell": 64, "rows": {"Down": 64, "Left": 128, "Right": 192, "Up": 256},
        "walk": [2, 3, 4, 5], "run": [2, 3, 4, 5],
        "attack": [7, 7, 8, 12, 12, 13, 14, 15, 15, 9, 16, 16],
        "hurt": [18, 19], "block": 17, "special": [14, 15, 15],
        "faint": [21, 27, 28, 28], "faint_row": "Down",
        "techniques": BROLY_TECHNIQUES,
    },
] + []  # the characters added from the second dbz-assets batch: NEW_SHEETS below

# Techniques of the characters whose effects come from EFFECTS_SHEET: name,
# kind, and the effect frames (boxes on that sheet, facing right)
FIREBALL = [[8, 8, 16, 16], [24, 8, 16, 16], [40, 8, 16, 16], [56, 8, 16, 16]]
PURPLE_SPARK = [[72, 8, 16, 16]]
YELLOW_BALL = [[8, 88, 8, 8], [16, 88, 16, 16], [32, 88, 16, 16]]
YELLOW_BLAST = [[48, 88, 32, 16], [80, 88, 32, 16], [112, 80, 32, 32], [144, 80, 32, 32]]
CROSS_SLASH = [[40, 272, 16, 16], [56, 272, 32, 32], [88, 272, 32, 32], [120, 272, 32, 32]]
GREEN_BALL = [[8, 200, 8, 8], [16, 200, 16, 16], [32, 200, 16, 16]]
GREEN_FLYING_BALL = [[48, 192, 32, 32], [80, 192, 32, 32], [112, 192, 32, 32]]
STAR_EXPLOSION = [[16, 232, 16, 16], [32, 232, 32, 32], [64, 232, 32, 32], [96, 232, 32, 32],
                  [128, 232, 32, 32]]
WHITE_RINGS = [[152, 200, 8, 8], [160, 200, 16, 16], [176, 192, 32, 32], [208, 192, 32, 32]]
FIRE_EXPLOSION = [[88, 136, 16, 16], [104, 128, 32, 32], [136, 128, 32, 32]]

NEW_SPECIALS = {
    "trunks": [
        ("energy_blast", "Energy Blast", "projectile", {"projectile": FIREBALL, "hit": PURPLE_SPARK}),
        ("burning_attack", "Burning Attack", "ball",
         {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:], "hit": YELLOW_BLAST}),
        ("sword_slash", "Sword Slash", "burst", {"rings": CROSS_SLASH}),
    ],
    "broly": [
        ("energy_blast", "Energy Blast", "projectile", {"projectile": FIREBALL, "hit": FIRE_EXPLOSION}),
        ("eraser_cannon", "Eraser Cannon", "ball",
         {"grow": GREEN_BALL, "projectile": GREEN_FLYING_BALL, "hit": STAR_EXPLOSION}),
        ("blaster_shell", "Blaster Shell", "burst", {"rings": WHITE_RINGS}),
    ],
}

# ---- Second batch of dbz-assets characters -------------------------------------
# Legacy of Goku 2 sheets (Piccolo, the androids, Cell) and Buu's Fury ones
# (the others); "no run" sheets reuse the walk, 64 px sheets are the big
# characters (Cell, the Buus). Columns read off each sheet.
BIG = {"cell": 64, "rows": {"Down": 64, "Left": 128, "Right": 192, "Up": 256}}
NO_RUN = [2, 3, 4, 5]
LOG2_ATTACK = [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 16]


def techniques(*entries):
    """{technique id: pose spec} from (id, columns, fire_at[, row])."""
    out = {}
    for entry in entries:
        technique_id, columns, fire_at = entry[:3]
        spec = {"pose": list(columns)}
        if fire_at is not None:
            spec["fire_at"] = fire_at
        if len(entry) > 3:
            spec["row"] = entry[3]
        out[technique_id] = spec
    return out


PICCOLO = dict(attack=[10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 20], hurt=[35, 36], block=34,
               special=[28, 29, 31], faint=[50, 51, 52, 53],
               techniques=techniques(("energy_blast", [28, 29, 31], 2), ("special_beam_cannon", [31, 32, 33, 33], 2),
                                     ("ki_burst", [23, 24, 25, 26], None)))
ANDROID = dict(run=NO_RUN, attack=LOG2_ATTACK, hurt=[17, 18], block=19, special=[21, 22, 20],
               faint=[25, 26, 27, 28],
               techniques=techniques(("energy_blast", [21, 22, 20], 2), ("power_blitz", [21, 22, 20], 2),
                                     ("barrier", [21, 22, 23], None)))
GOTEN = dict(hurt=[29, 30], block=28, special=[25, 26, 27], faint=[37, 38, 39, 40],
             techniques=techniques(("energy_blast", [25, 26, 27], 1), ("kamehameha", [20, 21, 22, 23, 24], 4),
                                   ("ki_burst", [24, 24], None)))
KID_TRUNKS = dict(hurt=[25, 26], block=27, special=[21, 22, 23], faint=[31, 32, 33, 34],
                  techniques=techniques(("energy_blast", [21, 22, 23], 1), ("burning_attack", [43, 44, 45], 2),
                                        ("ki_burst", [24, 24], None)))
GOTENKS = dict(hurt=[22, 23], block=24, special=[19, 20, 21], faint=[30, 31, 32, 33],
               techniques=techniques(("energy_blast", [19, 20, 21], 1),
                                     ("super_ghost_kamikaze", [36, 37, 38, 35], 3),
                                     ("galactic_donut", [34, 34], 1)))
# His ghost poses (crouching, then spitting the ghost out) face left on
# the sheets: mirrored for the right
SAIYAMAN = dict(hurt=[28, 29], block=27, special=[24, 25, 26], faint=[44, 45, 46, 47],
                # Kamehameha: hands drawn back to his hip (18), then thrust out (19)
                techniques=techniques(("energy_blast", [24, 25, 26], 1), ("kamehameha", [18, 18, 18, 19, 19], 3),
                                      ("ki_burst", [31], None)))
# Guard: 23, the forearm up in front of the face (26 is a hit, leaning back)
VEGITO = dict(hurt=[24, 25], block=23, special=[20, 21, 22], faint=[40, 41, 42, 43],
              techniques=techniques(("energy_blast", [20, 21, 22], 1), ("final_kamehameha", [21, 21, 22, 22], 4),
                                    ("spirit_sword", [30, 31, 32], 6)))
# Androids 16, 19 and 20 (Legacy of Goku 2): no run, the punches and
# kicks from column 6, a guard, a hand held out for their blasts
ANDROID_16 = dict(run=NO_RUN, attack=[10, 10, 11, 11, 12, 12, 13, 13, 10, 11, 12, 13], hurt=[15, 16],
                  block=14, special=[20, 10, 10], faint=[6, 7, 8, 9],
                  techniques=techniques(("energy_blast", [20, 10, 10], 1), ("hells_flash", [20, 20, 10, 10], 2),
                                        ("ki_burst", [17, 18], None)))
GERO_ANDROID = dict(run=NO_RUN, attack=LOG2_ATTACK[:-1] + [17], hurt=[21, 22], block=18, special=[19, 20, 20],
                    faint=[25, 26, 27, 28],
                    techniques=techniques(("eye_laser", [23, 23, 24], 1), ("photon_wave", [19, 20, 20], 2),
                                          ("energy_absorption", [19, 18], None)))
# Super Android 13 (Buu's Fury prototype): one grid of 64 px cells (cell n:
# column n % 10, row n // 10) facing front or left, so the side frames are
# mirrored for the right; Up uses the few drawn from behind
# Punches to the side (drawn facing left), uppercuts and swings facing front
_A13_SIDE_ATTACK = [22, 23, 23, 36, 29, 29, 53, 49, 49, 90, 91, 92]
_A13_FRONT_ATTACK = [24, 25, 26, 33, 34, 35, 28, 30, 31, 14, 18, 19]
# Shown as big as his sheet draws him. Hurt: shaking, sparks at his feet;
# knocked out: he breaks apart (his destruction frames)
ANDROID_13 = dict(cell=64, rows={"Down": 32, "Left": 32, "Right": 32, "Up": 32}, grid=10, flip_right=True,
                  idle={"Down": 0, "Right": 12, "Up": 10},
                  walk={"Down": [3, 4, 5, 6], "Right": [12, 13, 12, 13], "Up": [10, 11, 10, 60]},
                  run={"Down": [3, 4, 5, 6], "Right": [63, 64, 63, 64], "Up": [10, 11, 10, 60]},
                  attack={"Down": _A13_FRONT_ATTACK, "Right": _A13_SIDE_ATTACK, "Up": _A13_FRONT_ATTACK},
                  hurt=[76, 77], block=50,
                  special={"Down": [45, 46, 46], "Right": [12, 36, 36], "Up": [45, 46, 46]},
                  faint=[37, 38, 40, 42, 44], faint_row="Down",
                  techniques={"energy_blast": {"pose": {"Down": [45, 46, 46], "Right": [12, 36, 36],
                                                        "Up": [45, 46, 46]}, "fire_at": 1},
                              "sos_bomb": {"pose": [65, 66, 67, 68, 70, 71], "fire_at": 4, "row": "Down"},
                              "ki_burst": {"pose": [55, 51, 47], "row": "Down"}})
CELL_TECHNIQUES = (("energy_blast", [20, 21, 22], 1), ("kamehameha", [21, 22, 23], 2))

# ---- Third batch: Legacy of Goku 2 / Buu's Fury fighters, Goku Black ---------------
# Small LoG2 sheets: idle, walk 2-5, punches and kicks from 6, then hurt,
# guard, a pose for blasts, knocked out lying (no run: they walk faster)
KRILLIN = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 9, 10, 11, 11, 12, 12], hurt=[13, 14], block=16,
               special=[11, 12, 12], faint=[21, 22, 23, 24],
               techniques=techniques(("energy_blast", [11, 12, 12], 1), ("kamehameha", [11, 11, 12, 12], 2),
                                     ("destructo_disc", [18, 20, 20], 2)))
TIEN = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 10, 11, 11, 12, 12, 13], hurt=[17, 18], block=14,
            special=[15, 16, 16], faint=[25, 26, 27, 28],
            techniques=techniques(("energy_blast", [15, 16, 16], 1), ("dodon_ray", [15, 15, 16], 2),
                                  ("tri_beam", [16, 16, 16, 16], 2)))
YAMCHA = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 10, 11, 11, 12, 12, 13], hurt=[18, 19], block=17,
              special=[15, 16, 16], faint=[25, 26, 27, 28],
              techniques=techniques(("energy_blast", [15, 16, 16], 1), ("spirit_ball", [15, 16, 16], 2),
                                    ("wolf_fang_fist", [7, 8, 9, 10, 11, 12], None)))
# Cell Jr: idle, walk and four strikes only
CELL_JR = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 9, 6, 7, 7, 8, 9], hurt=[0, 1], block=0,
               special=[6, 7, 7], techniques=techniques(("energy_blast", [6, 7, 7], 1),
                                                        ("kamehameha", [6, 6, 7, 7], 2)))
# Frieza (final form) and Cooler (final form, a big 64 px sheet): the
# Death Beam from a fingertip (column 11 / 12), a ball held up (19)
FRIEZA = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 10, 12, 12, 15, 16, 17], hurt=[21, 22], block=23,
              special=[18, 20, 20],
              techniques=techniques(("energy_blast", [18, 20, 20], 1), ("death_beam", [11, 11, 11], 1),
                                    ("death_ball", [19, 19, 19, 20], 3)))
COOLER = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 10, 11, 12, 14, 15, 16], hurt=[21, 22], block=23,
              special=[18, 20, 20],
              techniques=techniques(("energy_blast", [18, 20, 20], 1), ("death_beam", [12, 12, 12], 1),
                                    ("supernova", [19, 19, 19, 20], 3)))
# Goku at the end of Z (Buu's Fury): an arm raised for the Spirit Bomb (18)
GOKU_END_OF_Z = dict(run=NO_RUN, attack=[6, 7, 7, 8, 8, 9, 10, 11, 11, 12, 12, 13], hurt=[15, 16], block=14,
                     special=[6, 7, 7], faint=[20, 21, 22, 23],
                     techniques=techniques(("energy_blast", [6, 7, 7], 1), ("kamehameha", [6, 6, 7, 7], 2),
                                           ("spirit_bomb", [18, 18, 18, 18], 3)))
# Big LoG2 sheets: run 6-9, twelve strikes from 10, then their own moves;
# their transformation is in the front row
LOG2_STRIKES = list(range(10, 22))
GOHAN_TEEN = dict(run=[6, 7, 8, 9], attack=LOG2_STRIKES, hurt=[35, 36], block=37, special=[28, 29, 30],
                  faint=[42, 43, 44, 45],
                  techniques=techniques(("energy_blast", [28, 29, 30], 1), ("kamehameha", [28, 28, 32, 33], 2),
                                        ("masenko", [39, 41, 30], 2)))
GOHAN_ULTIMATE = dict(run=[6, 7, 8, 9], attack=[10, 11, 11, 12, 12, 13, 14, 15, 15, 16, 16, 17], hurt=[28, 29],
                      block=30, special=[24, 25, 26], faint=[36, 37, 38, 39],
                      techniques=techniques(("energy_blast", [24, 25, 26], 1),
                                            ("kamehameha", [24, 24, 25, 26], 2), ("masenko", [31, 31, 26], 2)))
GOKU_LOG2 = dict(run=[6, 7, 8, 9], attack=LOG2_STRIKES, hurt=[39, 40], block=41, special=[35, 36, 37],
                 faint=[46, 47, 48, 49],
                 techniques={**techniques(("energy_blast", [35, 36, 37], 1), ("kamehameha", [28, 28, 29, 30], 2),
                                          ("spirit_bomb", [34, 34, 34, 34], 3)),
                             "instant_transmission": {"vanish": [23, 23, 23]}})
TRUNKS_FUTURE = dict(run=[6, 7, 8, 9], attack=LOG2_STRIKES, hurt=[36, 37], block=38, special=[29, 30, 31],
                     faint=[44, 45, 46, 47],
                     techniques=techniques(("energy_blast", [29, 30, 31], 1), ("burning_attack", [30, 31, 31], 1),
                                           ("sword_slash", [23, 24, 27, 33, 34, 35], None)))
VEGETA_LOG2 = dict(run=[6, 7, 8, 9], attack=LOG2_STRIKES, hurt=[35, 36], block=37, special=[28, 29, 29],
                   faint=[43, 44, 45, 46],
                   techniques=techniques(("energy_blast", [28, 29, 29], 1), ("big_bang", [27, 28, 29], 2),
                                         ("final_flash", [30, 31, 32, 33], 2)))
# Goku Black: no grid, each frame in a box of its own (detect_cells), rows
# front / right / left / back and one of his moves ("Extra": Kamehameha,
# Instant Transmission); Super Saiyan Rosé below, laid out the same
GOKU_BLACK_SHEET = "Graphics/assets/goku_black/sheet.png"
_BLACK_STRIKES = [6, 7, 7, 8, 8, 9, 10, 11, 11, 12, 13, 14]


def goku_black(top):
    """One form of Goku Black, its rows from y=top on his sheet."""
    bands = {"Down": (top, top + 33), "Right": (top + 34, top + 67), "Up": (top + 118, top + 151),
             "Extra": (top + 157, top + 190)}
    return dict(sheet=GOKU_BLACK_SHEET, cells={"bands": bands, "background": (0, 128, 128),
                                               "cell_background": (0, 64, 64)},
                clear=[(0, 128, 128), (0, 64, 64), (0, 80, 80)],
                walk=[1, 2, 3, 4], run=[1, 2, 3, 4], attack=_BLACK_STRIKES,
                hurt={"Down": [15, 16], "Right": [15, 16], "Up": [15, 15]},
                block={"Down": 17, "Right": 14, "Up": 16}, special=[6, 7, 7],
                techniques={**techniques(("energy_blast", [1, 4, 4], 1, "Extra"),
                                         ("black_kamehameha", [2, 3, 5, 6], 2, "Extra"),
                                         ("rose_sphere", [2, 3, 5, 6], 2, "Extra")),
                            "instant_transmission": {"vanish": [7, 8, 8], "row": "Extra"}})

NEW_SHEETS = [
    {"character": "piccolo", "form": "base", "transform": [56, 57, 57, 58, 59], **PICCOLO},
    {"character": "piccolo", "form": "ssj", **PICCOLO},
    {"character": "android17", "form": "base", **ANDROID},
    {"character": "android18", "form": "base", **ANDROID},
    {"character": "android13", "form": "base", **ANDROID_13},
    {"character": "krillin", "form": "base", **KRILLIN},
    {"character": "tien", "form": "base", **TIEN},
    {"character": "yamcha", "form": "base", **YAMCHA},
    {"character": "cell_jr", "form": "base", **CELL_JR},
    {"character": "frieza", "form": "base", **FRIEZA},
    {"character": "cooler", "form": "base", **BIG, **COOLER},
    {"character": "goku_end_of_z", "form": "base", **GOKU_END_OF_Z},
    {"character": "gohan_teen", "form": "base", "transform": [57, 58, 59, 60], **GOHAN_TEEN},
    {"character": "gohan_teen", "form": "ssj", "transform": [56, 57, 58, 59], **GOHAN_TEEN},
    {"character": "gohan_teen", "form": "ssj2", **{**GOHAN_TEEN, "faint": [43, 44, 45, 45]}},
    {"character": "gohan_ultimate", "form": "base", **GOHAN_ULTIMATE},
    {"character": "goku_log2", "form": "base", "transform": [60, 61, 62, 63], **GOKU_LOG2},
    {"character": "goku_log2", "form": "ssj", **GOKU_LOG2},
    {"character": "trunks_future", "form": "base", "transform": [58, 59, 60, 61], **TRUNKS_FUTURE},
    {"character": "trunks_future", "form": "ssj", **TRUNKS_FUTURE},
    {"character": "vegeta_log2", "form": "base", "transform": [57, 58, 59, 60], **VEGETA_LOG2},
    {"character": "vegeta_log2", "form": "ssj", **VEGETA_LOG2},
    {"character": "goku_black", "form": "base", **goku_black(4)},
    {"character": "goku_black", "form": "ssj", **goku_black(204)},
    {"character": "android16", "form": "base", **ANDROID_16},
    {"character": "android19", "form": "base", **GERO_ANDROID},
    {"character": "android20", "form": "base", **GERO_ANDROID},
    {"character": "goten", "form": "base", "transform": [52, 52, 53, 54, 55, 56], "fuse": [57, 58], **GOTEN},
    {"character": "goten", "form": "ssj", **GOTEN},
    {"character": "kid_trunks", "form": "base", "transform": [48, 48, 49, 50, 51], "fuse": [51, 52], **KID_TRUNKS},
    {"character": "kid_trunks", "form": "ssj", **KID_TRUNKS},
    # Gotenks is always a Super Saiyan; his SSJ sheet turns him into SSJ3.
    # Before he splits (the fusion's time is up) his hair goes back to black
    {"character": "gotenks", "form": "base", "transform": [48, 49, 50, 51, 52],
     **{**GOTENKS, "techniques": techniques(("energy_blast", [19, 20, 21], 1),
                                            ("super_ghost_kamikaze", [40, 41, 42, 39], 3),
                                            ("galactic_donut", [34, 34], 1))}},
    {"character": "gotenks", "form": "ssj", "transform": [42, 43, 44, 45], "defuse": [48, 49, 50], **GOTENKS},
    {"character": "gotenks", "form": "ssj3", "defuse": [43, 44, 45], **GOTENKS},
    {"character": "great_saiyaman", "form": "base", "transform": [57, 57, 58, 59, 60, 61], **SAIYAMAN},
    {"character": "great_saiyaman", "form": "ssj", **SAIYAMAN},
    {"character": "vegito", "form": "base", "transform": [32, 33, 33, 34, 35, 36], **VEGITO},
    {"character": "vegito", "form": "ssj", **VEGITO},
    # Gogeta is always a Super Saiyan; his black-haired frames are his
    # fusion running out
    {"character": "gogeta", "form": "ssj", "hurt": [29, 30], "block": 28, "special": [22, 23, 24],
     "faint": [37, 38, 39, 40], "defuse": [47, 48],
     "techniques": techniques(("energy_blast", [22, 23, 24], 1),
                              ("big_bang_kamehameha", [21, 22, 23, 24], 3),
                              ("soul_punisher", [45, 46, 46], 2, "Down"))},
    # Cell: the transformation frames turn him into his next form (played
    # while he absorbs an android, see the "evolve" techniques)
    {"character": "cell_imperfect", "form": "base", **BIG, "attack": list(range(6, 18)), "run": NO_RUN,
     "hurt": [27, 28], "block": 29, "special": [20, 21, 22], "faint": [32, 33, 34, 35],
     "transform": [24, 25, 26, 36, 37, 38, 39], "techniques": techniques(*CELL_TECHNIQUES)},
    {"character": "cell_semi_perfect", "form": "base", **BIG, "attack": list(range(6, 18)), "run": NO_RUN,
     "hurt": [28, 29], "block": 30, "special": [20, 21, 22], "faint": [32, 33, 34, 35],
     "transform": [24, 25, 36, 37, 38, 39, 42, 43], "techniques": techniques(*CELL_TECHNIQUES)},
    {"character": "cell_perfect", "form": "base", **BIG, "attack": list(range(6, 18)), "run": NO_RUN,
     "hurt": [24, 25], "block": 26, "special": [20, 21, 22], "faint": [32, 33, 34, 35],
     # His Super Kamehameha: a longer wind-up, hands cupped at his side
     "techniques": techniques(*CELL_TECHNIQUES, ("super_kamehameha", [21, 21, 21, 22, 23, 23], 4),
                              ("perfect_barrier", [26, 27], None))},
    # Majin Buu: walks on 1-4 (5 is his cape wrapped, not a step), guards
    # with 21, swings (6-9) then his flying tackle (16-17), raises his
    # arms for a blast (18-20), falls (38-40) and lies down (27)
    {"character": "buu", "form": "base", **BIG, "walk": [1, 2, 3, 4], "run": [1, 2, 3, 4],
     "attack": [6, 7, 7, 8, 8, 9, 9, 16, 17, 17, 6, 7], "hurt": [22, 23], "block": 21,
     "special": [18, 19, 20], "faint": [38, 39, 40, 27],
     "techniques": techniques(("energy_blast", [18, 19, 20], 2), ("candy_beam", [12, 13, 13], 1),
                              ("rage", [32, 33, 34, 35], None))},
    # (his Steam Rage: BUU_STEAM, added below)
    {"character": "kid_buu", "form": "base", "rows": {**ROWS, "Charge": 192}, "run": NO_RUN,
     "attack": list(range(6, 18)), "hurt": [18, 19], "block": 20, "special": [12, 12, 13],
     "faint": [21, 22, 23, 24],
     "techniques": techniques(("energy_blast", [12, 12, 13], 1), ("planet_burst", [1, 2, 3, 4], 3, "Charge"),
                              ("rage", [0, 1], None, "Charge"))},
    {"character": "super_buu", "form": "base", **BIG, "run": NO_RUN,
     "attack": [6, 7, 8, 9, 10, 10, 11, 12, 12, 16, 17, 18], "hurt": [23, 24], "block": 25,
     "special": [13, 14, 14], "faint": [31, 32, 33, 34],
     "techniques": techniques(("energy_blast", [13, 14, 14], 1), ("human_extinction", [36, 37, 37], 1),
                              ("rage", [38, 39, 40], None, "Down"))},
    {"character": "super_buu_gotenks", "form": "base", **BIG, "run": NO_RUN,
     "attack": [6, 7, 8, 9, 9, 10, 12, 13, 14, 15, 15, 6], "hurt": [18, 19], "block": 21,
     "special": [16, 17, 17], "faint": [22, 23, 24, 25],
     "techniques": techniques(("energy_blast", [16, 17, 17], 1), ("human_extinction", [26, 27, 28], 1),
                              ("rage", [29, 30, 31], None, "Down"))},
    {"character": "super_buu_gohan", "form": "base", **BIG, "run": NO_RUN,
     "attack": [6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 15, 6], "hurt": [27, 28], "block": 29,
     "special": [23, 24, 25], "faint": [35, 36, 37, 38],
     "techniques": techniques(("energy_blast", [23, 24, 25], 1), ("human_extinction", [39, 40, 41], 1),
                              ("rage", [42, 43, 44], None, "Down"))},
]
# Gotenks' ghost poses (crouching, then spitting the ghost out) face left
# on his sheets: mirrored for the right
for _sheet in NEW_SHEETS:
    if _sheet["character"] == "gotenks":
        _sheet["techniques"]["super_ghost_kamikaze"]["right_flip"] = True
SHEETS += NEW_SHEETS

# Effects borrowed from another character's techniques (read from its
# specials.json): (character, technique id)
BORROWED = {
    "gohan_beam": ("gohan", "kamehameha"),
    "gohan_blast": ("gohan", "energy_blast"),
    "gohan_burst": ("gohan", "ki_burst"),
    "final_flash": ("vegeta", "final_flash"),
    "big_bang": ("vegeta", "big_bang"),
}
# Buu's Fury sheets of Vegito, Gotenks and Majin Buu with their techniques'
# effects (setup.sh: Graphics/assets/effects/<name>_fx.gif), one background
# colour each; boxes read off the sheets
VEGITO_FX = f"{EFFECTS}/vegito_fx.gif"
GOTENKS_FX = f"{EFFECTS}/gotenks_fx.gif"
BUU_FX = f"{EFFECTS}/buu_fx.gif"
BF_BLUE = (13, 107, 247)
# Vegito's second effects sheet (its own transparency), drawn at about twice
# the game's size: its beam pieces are shrunk ("scale")
VEGITO_FX2 = f"{EFFECTS}/vegito_fx2.png"
VEGITO_FINAL_KAMEHAMEHA = {"beam": {"bodies": [[183, 1462, 66, 135], [567, 1473, 65, 135]],
                                    "head": [[284, 1453, 93, 157], [653, 1466, 103, 154]], "tile": True},
                           "scale": 0.22}
BUU_BLUE = (0, 6, 254)
VEGITO_EFFECTS = {
    "energy_blast": {"projectile": [[312, 303, 16, 16]],
                     "hit": [[290, 298, 14, 15], [340, 294, 14, 15], [362, 294, 16, 16]]},
}


def _held(boxes, times=3):
    """Each pose shown times as long (a sword swing is slower than a blast)."""
    return [box for box in boxes for _ in range(times)]


# Vegito's Final Kamehameha: hands cupped, a blue ball growing in them,
# then thrust out; from the side, from behind (the ball over his head) and
# from the front (the ball at his feet)
VEGITO_KAMEHAMEHA = {"sheet": VEGITO_FX, "background": BF_BLUE,
                     "boxes": {"Right": _held([[12, 342, 28, 31], [49, 342, 30, 31], [87, 342, 22, 31],
                                               [116, 342, 22, 31]], 2),
                               "Up": _held([[162, 379, 19, 35], [192, 377, 20, 37], [224, 383, 19, 31],
                                            [253, 383, 19, 31]], 2),
                               "Down": _held([[283, 382, 20, 31], [311, 380, 20, 33], [339, 383, 20, 31],
                                              [369, 383, 20, 31]], 2)}}
# Vegito with his Spirit Sword: from the side facing left (mirrored for the
# right), from the front (the blade down, hanging below his feet: the fifth
# number) and from behind (the blade up)
VEGITO_SWORD = {"sheet": VEGITO_FX, "background": BF_BLUE, "right_flip": True,
                "boxes": {"Right": _held([[6, 438, 32, 32], [49, 438, 32, 32], [95, 431, 40, 39], [150, 431, 40, 39],
                                          [199, 427, 44, 43], [257, 427, 44, 43]]),
                          "Down": _held([[99, 521, 38, 50, 18], [312, 438, 38, 50, 18], [224, 521, 15, 56, 24],
                                         [224, 521, 15, 56, 24]]),
                          "Up": _held([[47, 503, 37, 50], [357, 420, 37, 50], [18, 499, 15, 54], [18, 499, 15, 54]])}}

GOTENKS_EFFECTS = {
    "energy_blast": {"projectile": [[309, 294, 16, 16]],
                     "hit": [[287, 290, 13, 14], [337, 290, 13, 10], [398, 290, 13, 10]]},
    # The ghosts fly at the foe and burst in big yellow balls
    "super_ghost_kamikaze": {"grow": [[182, 335, 16, 30]], "projectile": [[206, 333, 16, 32], [230, 333, 16, 32]],
                             "hit": [[199, 466, 32, 32], [250, 447, 32, 32], [330, 449, 32, 32],
                                     [370, 448, 32, 32]]},
    # The ring thrown flat, a thin yellow line
    "galactic_donut": {"beam": {"full": [[247, 425, 48, 4]], "tail": 4, "head": 4}},
}
BUU_EFFECTS = {
    # From the antenna on his head, ending in the candy-making tip
    "candy_beam": {"beam": {"full": [[252, 167, 60, 10]], "tail": 4, "head": 16}},
}
# Buu fuming, steam out of his head (facing front, for every direction)
_BUU_STEAM = [[18, 679, 43, 58], [75, 688, 49, 49], [136, 680, 54, 56], [198, 676, 64, 63], [271, 674, 63, 64],
              [341, 672, 64, 64], [420, 676, 59, 63]]
BUU_STEAM = {"sheet": BUU_FX, "background": BUU_BLUE,
             "boxes": {"Down": _BUU_STEAM, "Right": _BUU_STEAM, "Up": _BUU_STEAM}}
# (both forms of Vegito share his techniques)
VEGITO["techniques"]["spirit_sword"]["pose_sheet"] = VEGITO_SWORD
VEGITO["techniques"]["final_kamehameha"]["pose_sheet"] = VEGITO_KAMEHAMEHA
next(s for s in NEW_SHEETS if s["character"] == "buu")["techniques"]["rage"]["pose_sheet"] = BUU_STEAM
# Gogeta's Fusion Dance (Vegeta on the left, Goku on the right): the dance,
# their fingers meeting, the light, Gogeta's white shape (then the flash)
FUSION_DANCE = {
    "sheet": f"{EFFECTS}/fusion_dance.png", "background": [0, 128, 0],
    "frames": [[18, 651, 48, 31], [93, 650, 47, 32], [164, 651, 59, 31], [248, 651, 56, 31], [326, 651, 46, 31],
               [402, 651, 46, 31], [474, 652, 48, 30], [549, 652, 46, 30], [14, 693, 54, 31], [91, 693, 52, 31],
               [160, 693, 63, 31], [249, 696, 52, 28], [325, 703, 51, 21], [399, 703, 51, 21], [474, 703, 51, 21],
               [549, 703, 51, 21], [17, 748, 51, 21], [93, 748, 51, 21], [166, 748, 51, 21], [243, 748, 51, 21],
               [325, 748, 51, 21], [445, 590, 16, 33]],
}

# Bigger and farther than their kind's usual (see techniques.py)
SIGNATURE = {"effect_scale": 2, "range_scale": 4}
# Bigger still (Cell's Super Kamehameha)
SUPER_SIGNATURE = {"effect_scale": 3, "range_scale": 5}

# Name, kind and effects of the new characters' techniques: effects frames
# on EFFECTS_SHEET, or ("borrow", key of BORROWED)
YELLOW_PROJECTILE = {"projectile": YELLOW_BALL[-1:], "hit": YELLOW_BLAST}
ENERGY_BLAST = ("Energy Blast", "projectile", {"projectile": FIREBALL, "hit": PURPLE_SPARK})
NEW_CHARACTER_SPECIALS = {
    "piccolo": {"energy_blast": ("Energy Blast", "projectile", YELLOW_PROJECTILE),
                "special_beam_cannon": ("Special Beam Cannon", "beam", ("borrow", "final_flash")),
                "ki_burst": ("Ki Burst", "burst", {"rings": WHITE_RINGS})},
    "android17": {"energy_blast": ENERGY_BLAST,
                  "power_blitz": ("Power Blitz", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                         "hit": YELLOW_BLAST}),
                  "barrier": ("Barrier", "burst", {"rings": WHITE_RINGS})},
    "android18": {"energy_blast": ENERGY_BLAST,
                  "power_blitz": ("Destructo Disc", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                            "hit": YELLOW_BLAST}),
                  "barrier": ("Barrier", "burst", {"rings": WHITE_RINGS})},
    "android13": {"energy_blast": ENERGY_BLAST,
                  "sos_bomb": ("S.O.S. Bomb", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                       "hit": STAR_EXPLOSION}),
                  "ki_burst": ("Ki Burst", "burst", {"rings": WHITE_RINGS})},
    "android16": {"energy_blast": ENERGY_BLAST,
                  "hells_flash": ("Hell's Flash", "beam", ("borrow", "final_flash")),
                  "ki_burst": ("Ki Burst", "burst", {"rings": WHITE_RINGS})},
    "android19": {"eye_laser": ("Eye Laser", "projectile", {"projectile": PURPLE_SPARK, "hit": PURPLE_SPARK}),
                  "photon_wave": ("Photon Wave", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                         "hit": YELLOW_BLAST}),
                  "energy_absorption": ("Energy Absorption", "burst", {"rings": WHITE_RINGS})},
    "goten": {"energy_blast": ("Energy Blast", "projectile", ("borrow", "gohan_blast")),
              "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam")),
              "ki_burst": ("Ki Burst", "burst", ("borrow", "gohan_burst"))},
    "kid_trunks": {"energy_blast": ENERGY_BLAST,
                   "burning_attack": ("Burning Attack", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                                "hit": YELLOW_BLAST}),
                   "ki_burst": ("Ki Burst", "burst", {"rings": WHITE_RINGS})},
    "gotenks": {"energy_blast": ("Energy Blast", "projectile",
                                 ("sheet", GOTENKS_FX, BF_BLUE, GOTENKS_EFFECTS["energy_blast"])),
                "super_ghost_kamikaze": ("Super Ghost Kamikaze Attack", "ball",
                                         ("sheet", GOTENKS_FX, BF_BLUE, GOTENKS_EFFECTS["super_ghost_kamikaze"])),
                "galactic_donut": ("Galactic Donut", "beam",
                                   ("sheet", GOTENKS_FX, BF_BLUE, GOTENKS_EFFECTS["galactic_donut"]))},
    "great_saiyaman": {"energy_blast": ("Energy Blast", "projectile", ("borrow", "gohan_blast")),
                       "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
                       "ki_burst": ("Ki Burst", "burst", ("borrow", "gohan_burst"))},
    "vegito": {"energy_blast": ("Energy Blast", "projectile",
                                ("sheet", VEGITO_FX, BF_BLUE, VEGITO_EFFECTS["energy_blast"])),
               # His Final Kamehameha (blue Kamehameha and yellow Final Flash
               # in one beam, from his second effects sheet), from his own
               # pose (VEGITO_KAMEHAMEHA)
               "final_kamehameha": ("Final Kamehameha", "beam",
                                    ("sheet", VEGITO_FX2, "alpha", VEGITO_FINAL_KAMEHAMEHA), SIGNATURE),
               # The blade is in his poses (VEGITO_SWORD): the cut itself
               # shows nothing more (blank cells of his sheet), it only hits
               "spirit_sword": ("Spirit Sword", "burst",
                                ("sheet", VEGITO_FX, BF_BLUE, {"rings": [[390, 4, 16, 16]] * 4}))},
    "gogeta": {"energy_blast": ENERGY_BLAST,
               "big_bang_kamehameha": ("Big Bang Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
               "soul_punisher": ("Soul Punisher", "ball", ("borrow", "big_bang"))},
    "cell_imperfect": {"energy_blast": ENERGY_BLAST,
                       "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"))},
    "cell_semi_perfect": {"energy_blast": ENERGY_BLAST,
                          "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"))},
    "cell_perfect": {"energy_blast": ENERGY_BLAST,
                     "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam")),
                     "super_kamehameha": ("Super Kamehameha", "beam", ("borrow", "gohan_beam"), SUPER_SIGNATURE),
                     "perfect_barrier": ("Perfect Barrier", "burst", {"rings": WHITE_RINGS})},
    "buu": {"energy_blast": ("Energy Blast", "projectile", {"projectile": FIREBALL, "hit": FIRE_EXPLOSION}),
            "candy_beam": ("Candy Beam", "beam", ("sheet", BUU_FX, BUU_BLUE, BUU_EFFECTS["candy_beam"])),
            "rage": ("Steam Rage", "burst", {"rings": WHITE_RINGS})},
    "kid_buu": {"energy_blast": ("Energy Blast", "projectile", {"projectile": FIREBALL, "hit": FIRE_EXPLOSION}),
                "planet_burst": ("Planet Burst", "ball", {"grow": GREEN_BALL, "projectile": GREEN_FLYING_BALL,
                                                         "hit": STAR_EXPLOSION}),
                "rage": ("Steam Rage", "burst", {"rings": WHITE_RINGS})},
}
NEW_CHARACTER_SPECIALS["android20"] = NEW_CHARACTER_SPECIALS["android19"]

# Goku Black's effects sheet (one background colour): a pink ki blast, the
# black and pink Kamehameha, a pink ki sphere; drawn at about twice the
# game's size ("scale")
GOKU_BLACK_FX = f"{EFFECTS}/goku_black_fx.png"
BLACK_BLUE = (87, 137, 170)
PINK_SPARK = [[651, 601, 13, 14], [672, 605, 6, 6]]
GOKU_BLACK_EFFECTS = {
    "energy_blast": {"projectile": [[414, 300, 82, 21]], "hit": PINK_SPARK, "scale": 0.45},
    "black_kamehameha": {"beam": {"start": [190, 448, 68, 62], "bodies": [[261, 463, 31, 32], [295, 464, 36, 30]],
                                  "head": [[333, 455, 65, 48], [401, 456, 60, 46]], "tile": True},
                         "scale": 0.5},
    "rose_sphere": {"grow": PINK_SPARK[::-1], "projectile": [[535, 564, 88, 89]],
                    "hit": [[377, 553, 112, 111], [92, 553, 112, 111]], "scale": 0.35},
}
FIRE_BALL = {"grow": [[8, 8, 16, 16], [24, 8, 16, 16]], "projectile": [[40, 8, 16, 16]], "hit": FIRE_EXPLOSION}
NEW_CHARACTER_SPECIALS.update({
    "krillin": {"energy_blast": ENERGY_BLAST,
                "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam")),
                "destructo_disc": ("Destructo Disc", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                             "hit": YELLOW_BLAST})},
    "tien": {"energy_blast": ENERGY_BLAST,
             "dodon_ray": ("Dodon Ray", "projectile", {"projectile": YELLOW_BALL[-1:], "hit": YELLOW_BLAST}),
             "tri_beam": ("Tri-Beam", "beam", ("borrow", "final_flash"), SIGNATURE)},
    "yamcha": {"energy_blast": ENERGY_BLAST,
               "spirit_ball": ("Spirit Ball", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                      "hit": YELLOW_BLAST}),
               "wolf_fang_fist": ("Wolf Fang Fist", "burst", {"rings": CROSS_SLASH})},
    "cell_jr": {"energy_blast": ENERGY_BLAST,
                "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"))},
    "frieza": {"energy_blast": ("Energy Blast", "projectile", {"projectile": PURPLE_SPARK, "hit": STAR_EXPLOSION}),
               "death_beam": ("Death Beam", "projectile", {"projectile": PURPLE_SPARK, "hit": PURPLE_SPARK}),
               "death_ball": ("Death Ball", "ball", FIRE_BALL, SIGNATURE)},
    "cooler": {"energy_blast": ("Energy Blast", "projectile", {"projectile": PURPLE_SPARK, "hit": STAR_EXPLOSION}),
               "death_beam": ("Death Beam", "projectile", {"projectile": PURPLE_SPARK, "hit": PURPLE_SPARK}),
               "supernova": ("Supernova", "ball", FIRE_BALL, SIGNATURE)},
    "goku_end_of_z": {"energy_blast": ENERGY_BLAST,
                      "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
                      "spirit_bomb": ("Spirit Bomb", "ball", ("borrow", "big_bang"), SIGNATURE)},
    "gohan_teen": {"energy_blast": ("Energy Blast", "projectile", ("borrow", "gohan_blast")),
                   "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
                   "masenko": ("Masenko", "beam", ("borrow", "final_flash"))},
    "gohan_ultimate": {"energy_blast": ("Energy Blast", "projectile", ("borrow", "gohan_blast")),
                       "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
                       "masenko": ("Masenko", "beam", ("borrow", "final_flash"))},
    "goku_log2": {"energy_blast": ENERGY_BLAST,
                  "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
                  "spirit_bomb": ("Spirit Bomb", "ball", ("borrow", "big_bang"), SIGNATURE),
                  "instant_transmission": ("Instant Transmission", "teleport", {})},
    "trunks_future": {"energy_blast": ENERGY_BLAST,
                      "burning_attack": ("Burning Attack", "ball", {"grow": YELLOW_BALL,
                                                                   "projectile": YELLOW_BALL[-1:],
                                                                   "hit": YELLOW_BLAST}),
                      "sword_slash": ("Sword Slash", "burst", {"rings": CROSS_SLASH})},
    "vegeta_log2": {"energy_blast": ENERGY_BLAST,
                    "big_bang": ("Big Bang Attack", "ball", ("borrow", "big_bang"), SIGNATURE),
                    "final_flash": ("Final Flash", "beam", ("borrow", "final_flash"), SIGNATURE)},
    "goku_black": {
        "energy_blast": ("Energy Blast", "projectile",
                         ("sheet", GOKU_BLACK_FX, BLACK_BLUE, GOKU_BLACK_EFFECTS["energy_blast"])),
        "black_kamehameha": ("Black Kamehameha", "beam",
                             ("sheet", GOKU_BLACK_FX, BLACK_BLUE, GOKU_BLACK_EFFECTS["black_kamehameha"]), SIGNATURE),
        "rose_sphere": ("Rosé Ki Sphere", "ball",
                        ("sheet", GOKU_BLACK_FX, BLACK_BLUE, GOKU_BLACK_EFFECTS["rose_sphere"])),
        "instant_transmission": ("Instant Transmission", "teleport", {})},
})
for _buu in ("super_buu", "super_buu_gotenks", "super_buu_gohan"):
    NEW_CHARACTER_SPECIALS[_buu] = {
        "energy_blast": ("Energy Blast", "projectile", {"projectile": FIREBALL, "hit": FIRE_EXPLOSION}),
        "human_extinction": ("Human Extinction Attack", "ball",
                             {"grow": GREEN_BALL, "projectile": GREEN_FLYING_BALL, "hit": STAR_EXPLOSION}),
        "rage": ("Steam Rage", "burst", {"rings": WHITE_RINGS}),
    }

# Techniques that turn the user into another character (techniques.py
# "evolve"): the partner who appears, how (a Potara fusion, or Cell
# absorbing an android), the character it becomes
# A fusion lasts lasts_s seconds, then the fighter is itself again and
# cannot fuse for cooldown_s seconds; an absorption is for good
FUSION_SECONDS = 60
FUSION_COOLDOWN_SECONDS = 90
EVOLVE = {
    "goku": [{"id": "potara", "name": "Potara Fusion (Vegito)", "kind": "evolve", "style": "fusion",
              "partner": "vegeta", "becomes": "vegito", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS},
             {"id": "fusion_gogeta", "name": "Fusion Dance (Gogeta)", "kind": "evolve", "style": "fusion",
              "partner": "vegeta", "becomes": "gogeta", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS, "dance": FUSION_DANCE}],
    "vegeta": [{"id": "potara", "name": "Potara Fusion (Vegito)", "kind": "evolve", "style": "fusion",
                "partner": "goku", "becomes": "vegito", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS},
               {"id": "fusion_gogeta", "name": "Fusion Dance (Gogeta)", "kind": "evolve", "style": "fusion",
                "partner": "goku", "becomes": "gogeta", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS, "dance": FUSION_DANCE}],
    "goten": [{"id": "fusion_dance", "name": "Fusion Dance", "kind": "evolve", "style": "fusion",
               "partner": "kid_trunks", "becomes": "gotenks", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS}],
    "kid_trunks": [{"id": "fusion_dance", "name": "Fusion Dance", "kind": "evolve", "style": "fusion",
                    "partner": "goten", "becomes": "gotenks", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS}],
    "cell_imperfect": [{"id": "absorb_17", "name": "Absorb Android 17", "kind": "evolve", "style": "absorb",
                        "partner": "android17", "becomes": "cell_semi_perfect"}],
    "cell_semi_perfect": [{"id": "absorb_18", "name": "Absorb Android 18", "kind": "evolve", "style": "absorb",
                           "partner": "android18", "becomes": "cell_perfect"}],
}


def borrowed_effects(key):
    character, technique_id = BORROWED[key]
    path = os.path.join(ROOT, "Config", "characters", character, "specials.json")
    with open(path) as file:
        specials = json.load(file)
    technique = next(t for t in specials["techniques"] if t["id"] == technique_id)
    form = next(iter(technique["forms"].values()))
    # The frames are on that character's effects sheet: keep which one
    return {**effects_only(form), "sheet": form["sheet"], "background": form["background"]}


def build_character_specials(character, form_poses):
    """Techniques of a second-batch character."""
    techniques = []
    for technique_id, entry in NEW_CHARACTER_SPECIALS[character].items():
        name, kind, effects = entry[:3]
        extra = entry[3] if len(entry) > 3 else {}
        if isinstance(effects, tuple) and effects[0] == "sheet":
            # Effects on a sheet of their own: ("sheet", path, background, frames)
            background = effects[2] if isinstance(effects[2], str) else list(effects[2])
            effects = {**effects[3], "sheet": effects[1], "background": background}
        elif isinstance(effects, tuple):
            effects = borrowed_effects(effects[1])  # with its own "sheet" and "background"
        else:
            effects = {**effects, "sheet": EFFECTS_SHEET, "background": "auto"}
        forms = {form: {**effects, **poses[technique_id]} for form, poses in form_poses.items()}
        techniques.append({"id": technique_id, "name": name, "kind": kind, **extra, "forms": forms})
    write_specials(character, {"techniques": techniques + EVOLVE.get(character, [])})


# Background colour of the spritedatabase.net sheets the effects come from
OLD_BACKGROUNDS = {
    "goku_ssj3": [0, 128, 0],
    "gohan_base": [0, 156, 255],
    "vegeta_ssj": [0, 128, 0],
}


def sheet_path(character, form):
    return f"Graphics/assets/{character}/{form}.png"


def _inside(image, box, colour, background):
    """box tightened to where colour is (a frame's own box on a sheet; a
    box of another shade: its own most common colour but the sheet's)."""
    x, y, width, height = box
    pixels = [(i, j, tuple(image.get_at((x + i, y + j)))[:3]) for j in range(height) for i in range(width)]
    if not any(c == colour for _, _, c in pixels):
        others = [c for _, _, c in pixels if c != background]
        if not others:
            return box
        colour = max(set(others), key=others.count)
    points = [(i, j) for i, j, c in pixels if c == colour]
    if not points:
        return box
    left, top = min(i for i, _ in points), min(j for _, j in points)
    right, bottom = max(i for i, _ in points), max(j for _, j in points)
    return [x + left, y + top, right - left + 1, bottom - top + 1]


def detect_cells(image, bands, background, cell_background=None):
    """{row: [[x, y, width, height]]}: the frames of a sheet that is no grid
    (each frame in a box of its own, of cell_background, on the
    background), row by row from the bands of rows they are in ({row: (top,
    bottom)}). Two touching boxes, too wide for one frame, are split in
    halves."""
    background = tuple(background)[:3]
    width = image.get_width()
    cells = {}
    for row, (top, bottom) in bands.items():
        filled = [any(tuple(image.get_at((x, y)))[:3] != background for y in range(top, bottom))
                  for x in range(width)]
        boxes = []
        x = 0
        while x < width:
            if not filled[x]:
                x += 1
                continue
            start = x
            while x < width and filled[x]:
                x += 1
            ys = [y for y in range(top, bottom) for column in range(start, x)
                  if tuple(image.get_at((column, y)))[:3] != background]
            box = [start, min(ys), x - start, max(ys) - min(ys) + 1]
            if box[2] > 40:
                half = box[2] // 2
                boxes += [[box[0], box[1], half, box[3]], [box[0] + half, box[1], box[2] - half, box[3]]]
            else:
                boxes.append(box)
        if cell_background is not None:
            boxes = [_inside(image, box, tuple(cell_background), background) for box in boxes]
        cells[row] = boxes
    return cells


class Sheet:
    def __init__(self, path, cell, rows, grid=None, cells=None):
        self.image = pygame.image.load(os.path.join(ROOT, path))
        self.path = path
        self.cell = cell
        self.rows = rows
        # A sheet of numbered cells instead of one row per direction: cell
        # n is column n % grid of row n // grid (from the direction's row)
        self.grid = grid
        # A sheet that is no grid at all: {row: [boxes]}, column n of a row
        # is its n-th box (see detect_cells)
        self.cells = detect_cells(self.image, cells["bands"], cells["background"],
                                  cells.get("cell_background")) if cells else None

    def box(self, column, row):
        """[x, y, width, height] of a frame of a sheet that is no grid."""
        return list(self.cells[row][column])

    def origin(self, column, row):
        """Top left corner of a cell."""
        if self.cells:
            return tuple(self.cells[row][column][:2])
        if self.grid:
            return (column % self.grid) * self.cell, self.rows[row] + (column // self.grid) * self.cell
        return column * self.cell, self.rows[row]

    def background(self, column, row):
        """The cell's own colour (the cells alternate two shades)."""
        if self.cells:
            x, y, width, height = self.cells[row][column]
            corners = [tuple(self.image.get_at((x + dx, y + dy)))[:3] for dx in (0, width - 1)
                       for dy in (0, height - 1)]
            return max(set(corners), key=corners.count)
        (x, y), size = self.origin(column, row), self.cell
        corners = [tuple(self.image.get_at((x + dx, y + dy)))[:3] for dx in (0, size - 1) for dy in (0, size - 1)]
        return max(set(corners), key=corners.count)

    def bounds(self, column, row):
        """Top and bottom rows of the sprite in a cell (None when empty)."""
        background = self.background(column, row)
        x, y = self.origin(column, row)
        rows = [dy for dy in range(self.cell) for dx in range(self.cell)
                if tuple(self.image.get_at((x + dx, y + dy)))[:3] != background]
        return (min(rows), max(rows)) if rows else None


def _is_light(colour):
    """A blade's or a glow's colour: light blue or white."""
    r, g, b = colour[:3]
    return (b > 180 and g > 150 and r < 200) or (r > 230 and g > 230 and b > 230)


def anchored(image, box, background):
    """[x, y, width, height, below, feet x]: box (below: how far the pose
    hangs below the feet) with the middle of the feet across it, from the
    lowest rows of the body (light blades and glows left out)."""
    x, y, width, height = box[:4]
    below = box[4] if len(box) > 4 else 0
    background = tuple(background)[:3]
    body = [(i, j) for j in range(height - below) for i in range(width)
            if tuple(image.get_at((x + i, y + j)))[:3] != background and not _is_light(image.get_at((x + i, y + j)))]
    if not body:
        return [x, y, width, height, below, width / 2]
    feet = max(j for _, j in body)
    across = [i for i, j in body if j >= feet - 4]
    return [x, y, width, height, below, round(sum(across) / len(across) + 0.5, 1)]


def frame(name, box, background, extra=None):
    x, y, width, height = box
    data = {"AnimationName": name, "x": x, "y": y, "Area Width": width, "Area Height": height,
            "Size": {"Width": width, "Height": height},
            "Background": {"R": background[0], "G": background[1], "B": background[2]}}
    data.update(extra or {})
    return data


def facing(value, row):
    """A move's columns (or column): the same for every direction, or
    {row: ...} (Down, Right, Up) when the sheet draws each its own way."""
    return value[row] if isinstance(value, dict) else value


def body_frames(spec):
    """(name, column, row) of every frame of the form."""
    frames = [(f"IDLE {direction}", facing(spec.get("idle", 0), SOURCE_ROW[direction]), SOURCE_ROW[direction])
              for direction in DIRECTIONS]
    moves = (("Walk", spec.get("walk", WALK)), ("Run", spec.get("run", RUN)),
             ("Attack", spec.get("attack", ATTACK)), ("Hurt", spec["hurt"]), ("Special", spec["special"]))
    for direction in DIRECTIONS:
        row = SOURCE_ROW[direction]
        for prefix, columns in moves:
            frames += [(f"{prefix} {direction} {i}", c, row) for i, c in enumerate(facing(columns, row))]
        frames.append((f"Block {direction} 0", facing(spec["block"], row), row))
    faint_row = spec.get("faint_row", "Right")
    frames += [(f"Faint {i}", c, faint_row) for i, c in enumerate(spec.get("faint", []))]
    frames += [(f"Transform {i}", c, "Down") for i, c in enumerate(spec.get("transform", []))]
    # A fusion: glowing as it merges (per direction), and the fused
    # character powering down before it splits again (facing front)
    for direction in DIRECTIONS:
        frames += [(f"Fuse {direction} {i}", c, SOURCE_ROW[direction]) for i, c in enumerate(spec.get("fuse", []))]
    frames += [(f"Defuse {i}", c, "Down") for i, c in enumerate(spec.get("defuse", []))]
    return frames


def technique_cells(technique):
    """{direction: [(column, row)]} of a technique's poses."""
    poses = technique.get("pose") or technique.get("vanish")
    if isinstance(poses, list):
        poses = {direction: poses for direction in ("Down", "Right", "Up")}
    return {direction: [(c, technique.get("row", direction)) for c in columns]
            for direction, columns in poses.items()}


def build_form(spec):
    sheet = Sheet(spec.get("sheet") or sheet_path(spec["character"], spec["form"]), spec.get("cell", CELL),
                  spec.get("rows", ROWS),
                  spec.get("grid"), spec.get("cells"))
    # Sheets drawing the side frames facing left: the game's "Right" frames
    # are those, mirrored
    flip_right = spec.get("flip_right", False)
    frames = body_frames(spec)
    cells = {(c, row) for _, c, row in frames}
    for technique in spec["techniques"].values():
        for pose_cells in technique_cells(technique).values():
            cells |= set(pose_cells)
    # One crop for the whole sheet, so every frame lines up (feet on the
    # same row) and nothing jumps from one frame to the next
    if sheet.cells:
        # Frames in boxes of their own: each box as it is
        box = sheet.box
    else:
        bounds = [b for b in (sheet.bounds(c, row) for c, row in cells) if b]
        top = min(b[0] for b in bounds)
        bottom = max(b[1] for b in bounds)

        def box(column, row):
            x, y = sheet.origin(column, row)
            return [x, y + top, sheet.cell, bottom - top + 1]

    animations = [frame(name, box(c, row), sheet.background(c, row),
                        {"Flip": True} if flip_right and row == "Right" else None) for name, c, row in frames]
    old = spec.get("transform_old")
    if old:
        animations += [frame(f"Transform {i}", b, old["background"], {"Sheet": old["sheet"]})
                       for i, b in enumerate(old["boxes"])]
    config = {"Character": spec["character"], "Image path": sheet.path, "Animations": animations}
    if "scale" in spec:
        config["Scale"] = spec["scale"]
    if "clear" in spec:
        config["Clear"] = [list(colour) for colour in spec["clear"]]
    path = os.path.join(ROOT, "Config", "characters", spec["character"], f"{spec['form']}.json")
    with open(path, "w") as file:
        json.dump(config, file, indent=2)
        file.write("\n")

    poses = {}
    for technique_id, technique in spec["techniques"].items():
        key = "vanish" if "vanish" in technique else "pose"
        boxes = {d: [box(c, row) for c, row in pose_cells] for d, pose_cells in technique_cells(technique).items()}
        if flip_right or technique.get("right_flip"):
            boxes["right_flip"] = True
        poses[technique_id] = {key: boxes, **({"fire_at": technique["fire_at"]} if "fire_at" in technique else {})}
        elsewhere = technique.get("pose_sheet")
        if elsewhere:
            # Poses of some directions drawn on another sheet (with their
            # effect: a sword, steam), as boxes there, with where the feet
            # are across each (they stay where the character stands)
            other = Sheet(elsewhere["sheet"], CELL, ROWS)
            boxes.update({direction: [anchored(other.image, box, elsewhere["background"]) for box in direction_boxes]
                          for direction, direction_boxes in elsewhere["boxes"].items()})
            poses[technique_id]["pose_sheet"] = {
                "sheet": elsewhere["sheet"], "background": list(elsewhere["background"]),
                "directions": list(elsewhere["boxes"]), "right_flip": elsewhere.get("right_flip", False)}
    return poses


def old_background(character, form):
    return OLD_BACKGROUNDS[f"{character}_{form}"]


POSE_KEYS = ("pose", "vanish", "fire_at", "right_flip", "sheet", "background", "pose_sheet")


def effects_only(form_data):
    return {k: v for k, v in form_data.items() if k not in POSE_KEYS}


def write_specials(character, specials):
    path = os.path.join(ROOT, "Config", "characters", character, "specials.json")
    with open(path, "w") as file:
        json.dump(specials, file, indent=2)
        file.write("\n")


def update_specials(character, form_poses, effects):
    """Techniques with spritedatabase.net effects: new poses, same effects."""
    path = os.path.join(ROOT, "Config", "characters", character, "specials.json")
    with open(path) as file:
        specials = json.load(file)
    for technique in specials["techniques"]:
        if "forms" not in technique:
            continue  # an "evolve" technique: no sprites of its own
        forms = technique["forms"]
        for form, poses in form_poses.items():
            if technique["id"] not in poses:
                continue
            source = effects[form]
            entry = effects_only(forms.get(source["from_form"]) or forms.get(form) or {})
            entry.update(poses[technique["id"]])
            entry["sheet"] = source["sheet"]
            entry["background"] = source["background"]
            forms[form] = entry
    # The evolve techniques as EVOLVE says now (replacing older entries)
    evolve = EVOLVE.get(character, [])
    ids = {technique["id"] for technique in evolve}
    specials["techniques"] = [t for t in specials["techniques"] if t["id"] not in ids] + evolve
    write_specials(character, specials)


def build_new_specials(character, form_poses):
    """Techniques with effects from EFFECTS_SHEET."""
    techniques = []
    for technique_id, name, kind, effects in NEW_SPECIALS[character]:
        forms = {}
        for form, poses in form_poses.items():
            forms[form] = {**effects, **poses[technique_id], "sheet": EFFECTS_SHEET, "background": "auto"}
        techniques.append({"id": technique_id, "name": name, "kind": kind, "forms": forms})
    write_specials(character, {"techniques": techniques})


def main():
    pygame.init()
    poses_by_character = {}
    effects_by_character = {}
    for spec in SHEETS:
        os.makedirs(os.path.join(ROOT, "Config", "characters", spec["character"]), exist_ok=True)
        poses = build_form(spec)
        poses_by_character.setdefault(spec["character"], {})[spec["form"]] = poses
        if "effects" in spec:
            source = spec["effects"]
            character, form = os.path.basename(source["sheet"])[:-4].split("_")
            effects_by_character.setdefault(spec["character"], {})[spec["form"]] = {
                **source, "background": old_background(character, form)}
        print(f"{spec['character']}/{spec['form']}: written")
    for character, form_poses in poses_by_character.items():
        if character in NEW_SPECIALS:
            build_new_specials(character, form_poses)
        elif character in NEW_CHARACTER_SPECIALS:
            build_character_specials(character, form_poses)
        else:
            update_specials(character, form_poses, effects_by_character[character])
    print("specials updated")


if __name__ == "__main__":
    sys.exit(main())
