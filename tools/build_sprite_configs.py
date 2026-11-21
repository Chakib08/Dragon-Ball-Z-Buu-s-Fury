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
                                     ("super_ghost_kamikaze", [35, 36, 37, 38], 3),
                                     ("galactic_donut", [34, 34], None)))
SAIYAMAN = dict(hurt=[28, 29], block=27, special=[24, 25, 26], faint=[44, 45, 46, 47],
                techniques=techniques(("energy_blast", [24, 25, 26], 1), ("kamehameha", [22, 23, 24], 2),
                                      ("ki_burst", [31], None)))
VEGITO = dict(hurt=[24, 25], block=26, special=[20, 21, 22], faint=[40, 41, 42, 43],
              techniques=techniques(("energy_blast", [20, 21, 22], 1), ("final_kamehameha", [21, 22, 22, 23], 2),
                                    ("spirit_sword", [30, 31, 32], None)))
CELL_TECHNIQUES = (("energy_blast", [20, 21, 22], 1), ("kamehameha", [21, 22, 23], 2))

NEW_SHEETS = [
    {"character": "piccolo", "form": "base", "transform": [56, 57, 57, 58, 59], **PICCOLO},
    {"character": "piccolo", "form": "ssj", **PICCOLO},
    {"character": "android17", "form": "base", **ANDROID},
    {"character": "android18", "form": "base", **ANDROID},
    {"character": "goten", "form": "base", "transform": [52, 52, 53, 54, 55, 56], "fuse": [57, 58], **GOTEN},
    {"character": "goten", "form": "ssj", **GOTEN},
    {"character": "kid_trunks", "form": "base", "transform": [48, 48, 49, 50, 51], "fuse": [51, 52], **KID_TRUNKS},
    {"character": "kid_trunks", "form": "ssj", **KID_TRUNKS},
    # Gotenks is always a Super Saiyan; his SSJ sheet turns him into SSJ3.
    # Before he splits (the fusion's time is up) his hair goes back to black
    {"character": "gotenks", "form": "base", "transform": [48, 49, 50, 51, 52],
     **{**GOTENKS, "techniques": techniques(("energy_blast", [19, 20, 21], 1),
                                            ("super_ghost_kamikaze", [39, 40, 41, 42], 3),
                                            ("galactic_donut", [34, 34], None))}},
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
     "techniques": techniques(*CELL_TECHNIQUES, ("perfect_barrier", [26, 27], None))},
    {"character": "buu", "form": "base", **BIG, "run": NO_RUN,
     "attack": [6, 7, 7, 8, 8, 9, 14, 15, 15, 6, 7, 7], "hurt": [22, 23], "block": 24,
     "special": [18, 18, 19], "faint": [36, 37, 38, 39],
     "techniques": techniques(("energy_blast", [18, 18, 19], 1), ("candy_beam", [12, 13, 13], 1),
                              ("rage", [32, 33, 34, 35], None))},
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
# Bigger and farther than their kind's usual (see techniques.py)
SIGNATURE = {"effect_scale": 2, "range_scale": 4}

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
    "goten": {"energy_blast": ("Energy Blast", "projectile", ("borrow", "gohan_blast")),
              "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam")),
              "ki_burst": ("Ki Burst", "burst", ("borrow", "gohan_burst"))},
    "kid_trunks": {"energy_blast": ENERGY_BLAST,
                   "burning_attack": ("Burning Attack", "ball", {"grow": YELLOW_BALL, "projectile": YELLOW_BALL[-1:],
                                                                "hit": YELLOW_BLAST}),
                   "ki_burst": ("Ki Burst", "burst", {"rings": WHITE_RINGS})},
    "gotenks": {"energy_blast": ENERGY_BLAST,
                "super_ghost_kamikaze": ("Super Ghost Kamikaze Attack", "ball",
                                         {"grow": WHITE_RINGS[:2], "projectile": WHITE_RINGS[-1:],
                                          "hit": STAR_EXPLOSION}),
                "galactic_donut": ("Galactic Donut", "burst", {"rings": WHITE_RINGS})},
    "great_saiyaman": {"energy_blast": ("Energy Blast", "projectile", ("borrow", "gohan_blast")),
                       "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam")),
                       "ki_burst": ("Ki Burst", "burst", ("borrow", "gohan_burst"))},
    "vegito": {"energy_blast": ENERGY_BLAST,
               "final_kamehameha": ("Final Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
               "spirit_sword": ("Spirit Sword", "burst", {"rings": CROSS_SLASH})},
    "gogeta": {"energy_blast": ENERGY_BLAST,
               "big_bang_kamehameha": ("Big Bang Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
               "soul_punisher": ("Soul Punisher", "ball", ("borrow", "big_bang"))},
    "cell_imperfect": {"energy_blast": ENERGY_BLAST,
                       "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"))},
    "cell_semi_perfect": {"energy_blast": ENERGY_BLAST,
                          "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"))},
    "cell_perfect": {"energy_blast": ENERGY_BLAST,
                     "kamehameha": ("Kamehameha", "beam", ("borrow", "gohan_beam"), SIGNATURE),
                     "perfect_barrier": ("Perfect Barrier", "burst", {"rings": WHITE_RINGS})},
    "buu": {"energy_blast": ("Energy Blast", "projectile", {"projectile": FIREBALL, "hit": FIRE_EXPLOSION}),
            "candy_beam": ("Candy Beam", "projectile", {"projectile": PURPLE_SPARK, "hit": STAR_EXPLOSION}),
            "rage": ("Steam Rage", "burst", {"rings": WHITE_RINGS})},
    "kid_buu": {"energy_blast": ("Energy Blast", "projectile", {"projectile": FIREBALL, "hit": FIRE_EXPLOSION}),
                "planet_burst": ("Planet Burst", "ball", {"grow": GREEN_BALL, "projectile": GREEN_FLYING_BALL,
                                                         "hit": STAR_EXPLOSION}),
                "rage": ("Steam Rage", "burst", {"rings": WHITE_RINGS})},
}
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
              "cooldown_s": FUSION_COOLDOWN_SECONDS}],
    "vegeta": [{"id": "potara", "name": "Potara Fusion (Vegito)", "kind": "evolve", "style": "fusion",
                "partner": "goku", "becomes": "vegito", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS},
               {"id": "fusion_gogeta", "name": "Fusion Dance (Gogeta)", "kind": "evolve", "style": "fusion",
                "partner": "goku", "becomes": "gogeta", "lasts_s": FUSION_SECONDS,
              "cooldown_s": FUSION_COOLDOWN_SECONDS}],
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
        if isinstance(effects, tuple):
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


class Sheet:
    def __init__(self, path, cell, rows):
        self.image = pygame.image.load(os.path.join(ROOT, path))
        self.path = path
        self.cell = cell
        self.rows = rows

    def background(self, column, row):
        """The cell's own colour (the cells alternate two shades)."""
        x, y, size = column * self.cell, self.rows[row], self.cell
        corners = [tuple(self.image.get_at((x + dx, y + dy)))[:3] for dx in (0, size - 1) for dy in (0, size - 1)]
        return max(set(corners), key=corners.count)

    def bounds(self, column, row):
        """Top and bottom rows of the sprite in a cell (None when empty)."""
        background = self.background(column, row)
        x, y = column * self.cell, self.rows[row]
        rows = [dy for dy in range(self.cell) for dx in range(self.cell)
                if tuple(self.image.get_at((x + dx, y + dy)))[:3] != background]
        return (min(rows), max(rows)) if rows else None


def frame(name, box, background, extra=None):
    x, y, width, height = box
    data = {"AnimationName": name, "x": x, "y": y, "Area Width": width, "Area Height": height,
            "Size": {"Width": width, "Height": height},
            "Background": {"R": background[0], "G": background[1], "B": background[2]}}
    data.update(extra or {})
    return data


def body_frames(spec):
    """(name, column, row) of every frame of the form."""
    frames = [(f"IDLE {direction}", 0, SOURCE_ROW[direction]) for direction in DIRECTIONS]
    moves = (("Walk", spec.get("walk", WALK)), ("Run", spec.get("run", RUN)),
             ("Attack", spec.get("attack", ATTACK)), ("Hurt", spec["hurt"]), ("Special", spec["special"]))
    for direction in DIRECTIONS:
        row = SOURCE_ROW[direction]
        for prefix, columns in moves:
            frames += [(f"{prefix} {direction} {i}", c, row) for i, c in enumerate(columns)]
        frames.append((f"Block {direction} 0", spec["block"], row))
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
    sheet = Sheet(sheet_path(spec["character"], spec["form"]), spec.get("cell", CELL), spec.get("rows", ROWS))
    frames = body_frames(spec)
    cells = {(c, row) for _, c, row in frames}
    for technique in spec["techniques"].values():
        for pose_cells in technique_cells(technique).values():
            cells |= set(pose_cells)
    # One crop for the whole sheet, so every frame lines up (feet on the
    # same row) and nothing jumps from one frame to the next
    bounds = [b for b in (sheet.bounds(c, row) for c, row in cells) if b]
    top = min(b[0] for b in bounds)
    bottom = max(b[1] for b in bounds)

    def box(column, row):
        return [column * sheet.cell, sheet.rows[row] + top, sheet.cell, bottom - top + 1]

    animations = [frame(name, box(c, row), sheet.background(c, row)) for name, c, row in frames]
    old = spec.get("transform_old")
    if old:
        animations += [frame(f"Transform {i}", b, old["background"], {"Sheet": old["sheet"]})
                       for i, b in enumerate(old["boxes"])]
    config = {"Character": spec["character"], "Image path": sheet.path, "Animations": animations}
    path = os.path.join(ROOT, "Config", "characters", spec["character"], f"{spec['form']}.json")
    with open(path, "w") as file:
        json.dump(config, file, indent=2)
        file.write("\n")

    poses = {}
    for technique_id, technique in spec["techniques"].items():
        key = "vanish" if "vanish" in technique else "pose"
        boxes = {d: [box(c, row) for c, row in pose_cells] for d, pose_cells in technique_cells(technique).items()}
        poses[technique_id] = {key: boxes, **({"fire_at": technique["fire_at"]} if "fire_at" in technique else {})}
    return poses


def old_background(character, form):
    return OLD_BACKGROUNDS[f"{character}_{form}"]


POSE_KEYS = ("pose", "vanish", "fire_at", "right_flip", "sheet", "background")


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
