#!/usr/bin/env python3
"""Extract graphics from a GBA ROM you dumped from your own cartridge.

GBA games store graphics as 8x8 pixel tiles (4 or 8 bits per pixel) and
colour palettes (15-bit BGR). Many games compress them with the BIOS LZ77
format. This tool finds that data and renders it as PNG sheets you can
browse to locate characters. It does not know any game's own layout, so the
sheets show raw tiles, not assembled sprite frames.

Commands
    scan      find LZ77/RLE-compressed blocks and render each one
    raw       render an uncompressed region of the ROM as tiles
    palettes  list likely 16-colour palettes (to colour the tiles)

Examples
    python3 tools/gba_rip.py scan rom.gba rips/
    python3 tools/gba_rip.py raw rom.gba rips/ --start 0x200000 --length 0x10000
    python3 tools/gba_rip.py palettes rom.gba --limit 40
    python3 tools/gba_rip.py scan rom.gba rips/ --palette 0x3A1F20

Never commit the ROM or the output: both are the game's copyrighted data.
"""

import argparse
import html
import os
import struct
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402  (the environment variables must be set first)

TILE = 8
ROM_BASE = 0x08000000  # where the cartridge appears in the GBA's memory map


# ---- Decompression (GBA BIOS formats) -------------------------------------------
class DecompressError(ValueError):
    pass


def _header(data, offset, kind):
    if offset + 4 > len(data) or data[offset] != kind:
        raise DecompressError("no header")
    return int.from_bytes(data[offset + 1:offset + 4], "little")


def lz77_decompress(data, offset, max_size):
    """BIOS LZ77 (type 0x10). Returns (decompressed bytes, compressed length)."""
    size = _header(data, offset, 0x10)
    if not 0 < size <= max_size:
        raise DecompressError("implausible size")
    out = bytearray()
    pos = offset + 4
    while len(out) < size:
        if pos >= len(data):
            raise DecompressError("truncated")
        flags = data[pos]
        pos += 1
        for bit in range(8):
            if len(out) >= size:
                break
            if flags & (0x80 >> bit):
                if pos + 1 >= len(data):
                    raise DecompressError("truncated")
                length = (data[pos] >> 4) + 3
                distance = (((data[pos] & 0x0F) << 8) | data[pos + 1]) + 1
                pos += 2
                if distance > len(out):
                    raise DecompressError("reference before start")
                for _ in range(length):
                    out.append(out[-distance])
            else:
                if pos >= len(data):
                    raise DecompressError("truncated")
                out.append(data[pos])
                pos += 1
    return bytes(out[:size]), pos - offset


def rle_decompress(data, offset, max_size):
    """BIOS run-length (type 0x30). Returns (decompressed bytes, compressed length)."""
    size = _header(data, offset, 0x30)
    if not 0 < size <= max_size:
        raise DecompressError("implausible size")
    out = bytearray()
    pos = offset + 4
    while len(out) < size:
        if pos >= len(data):
            raise DecompressError("truncated")
        flag = data[pos]
        pos += 1
        if flag & 0x80:
            if pos >= len(data):
                raise DecompressError("truncated")
            out += bytes([data[pos]]) * ((flag & 0x7F) + 3)
            pos += 1
        else:
            length = (flag & 0x7F) + 1
            if pos + length > len(data):
                raise DecompressError("truncated")
            out += data[pos:pos + length]
            pos += length
    return bytes(out[:size]), pos - offset


DECOMPRESSORS = {0x10: ("lz77", lz77_decompress), 0x30: ("rle", rle_decompress)}


# Real graphics shrink when compressed; random bytes that happen to parse
# as a compressed block barely do
MIN_RATIO = 1.3


def find_compressed(rom, min_size, max_size, align=4, kinds=(0x10,)):
    """Yield (offset, kind, data) for every block that decompresses cleanly.

    The BIOS needs compressed data 4-byte aligned, which also removes most
    false positives. Blocks found inside a previous block are skipped.
    """
    offset = 0
    while offset < len(rom) - 4:
        entry = DECOMPRESSORS.get(rom[offset]) if rom[offset] in kinds else None
        if entry is not None:
            kind, decompress = entry
            try:
                data, used = decompress(rom, offset, max_size)
            except DecompressError:
                data = None
            if data is not None and len(data) >= min_size and used * MIN_RATIO <= len(data):
                yield offset, kind, data
                offset += (used + align - 1) // align * align
                continue
        offset += align


# ---- Palettes ---------------------------------------------------------------------
def bgr555_to_rgb(value):
    return (
        (value & 0x1F) * 255 // 31,
        ((value >> 5) & 0x1F) * 255 // 31,
        ((value >> 10) & 0x1F) * 255 // 31,
    )


def read_palette(rom, offset, colours=16):
    values = struct.unpack_from(f"<{colours}H", rom, offset)
    return [bgr555_to_rgb(value) for value in values]


def grey_palette(colours):
    step = 255 // (colours - 1)
    return [(index * step, index * step, index * step) for index in range(colours)]


def find_palettes(rom, limit):
    """Score every 4-byte aligned 32-byte block as a possible 16-colour palette.

    Palette entries never use bit 15, mostly differ from each other, and
    sprite palettes often start with the transparent colour.
    """
    candidates = []
    for offset in range(0, len(rom) - 32, 4):
        values = struct.unpack_from("<16H", rom, offset)
        if any(value & 0x8000 for value in values):
            continue
        distinct = len(set(values))
        if distinct < 10:
            continue
        # Colours with all three channels non-trivial look like real artwork
        lively = sum(1 for value in values if value not in (0, 0x7FFF))
        score = distinct + lively / 4
        candidates.append((score, offset))
    candidates.sort(reverse=True)
    return [offset for _, offset in candidates[:limit]]


# ---- Rendering ----------------------------------------------------------------------
def render_tiles(data, bpp, palette, tiles_per_row, transparent=True):
    """Draw raw tile data on a surface, tiles_per_row tiles across."""
    tile_bytes = TILE * TILE * bpp // 8
    count = len(data) // tile_bytes
    if count == 0:
        return None
    rows = (count + tiles_per_row - 1) // tiles_per_row
    surface = pygame.Surface((tiles_per_row * TILE, rows * TILE))
    surface.fill((255, 0, 255))
    pixels = pygame.PixelArray(surface)
    colours = [surface.map_rgb(colour) for colour in palette]
    for tile in range(count):
        base = tile * tile_bytes
        tile_x = (tile % tiles_per_row) * TILE
        tile_y = (tile // tiles_per_row) * TILE
        for index in range(TILE * TILE):
            if bpp == 4:
                byte = data[base + index // 2]
                value = (byte >> 4) if index & 1 else (byte & 0x0F)
            else:
                value = data[base + index]
            if value >= len(colours):
                value %= len(colours)
            pixels[tile_x + index % TILE, tile_y + index // TILE] = colours[value]
    del pixels
    if transparent:
        surface.set_colorkey(palette[0])
    return surface


def save_scaled(surface, path, scale):
    if scale > 1:
        surface = pygame.transform.scale(
            surface, (surface.get_width() * scale, surface.get_height() * scale)
        )
    pygame.image.save(surface, path)


def write_index(out_dir, entries, title):
    """A small HTML page to browse the sheets with their ROM offsets."""
    rows = "\n".join(
        f'<figure><img src="{html.escape(name)}" loading="lazy">'
        f"<figcaption>{html.escape(caption)}</figcaption></figure>"
        for name, caption in entries
    )
    page = f"""<!doctype html>
<meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
 body {{ background:#222; color:#ddd; font:14px sans-serif; margin:16px }}
 figure {{ display:inline-block; margin:8px; vertical-align:top;
          background:#333; padding:6px }}
 img {{ image-rendering:pixelated; display:block; max-width:90vw }}
</style>
<h1>{html.escape(title)}</h1>
{rows}
"""
    with open(os.path.join(out_dir, "index.html"), "w") as file:
        file.write(page)


# ---- Commands -----------------------------------------------------------------------
def load_rom(path):
    with open(path, "rb") as file:
        rom = file.read()
    if len(rom) < 0xC0 or rom[0xB2] != 0x96:
        print(f"warning: {path} does not look like a GBA ROM", file=sys.stderr)
    else:
        title = rom[0xA0:0xAC].rstrip(b"\0").decode("ascii", "replace")
        code = rom[0xAC:0xB0].decode("ascii", "replace")
        print(f"ROM: {title} ({code}), {len(rom) / 1024 / 1024:.1f} MiB")
    return rom


def palette_for(rom, args, bpp):
    colours = 16 if bpp == 4 else 256
    if args.palette is None:
        return grey_palette(colours)
    return read_palette(rom, args.palette, colours)


def command_scan(args):
    rom = load_rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    palette = palette_for(rom, args, args.bpp)
    entries = []
    kinds = (0x10, 0x30) if args.rle else (0x10,)
    for offset, kind, data in find_compressed(rom, args.min_size, args.max_size, kinds=kinds):
        surface = render_tiles(data, args.bpp, palette, args.width)
        if surface is None:
            continue
        name = f"{kind}_{offset:07X}.png"
        save_scaled(surface, os.path.join(args.out, name), args.scale)
        if args.save_data:
            with open(os.path.join(args.out, f"{kind}_{offset:07X}.bin"), "wb") as file:
                file.write(data)
        entries.append((name, f"{kind} at 0x{offset:07X} (0x{ROM_BASE + offset:08X}), {len(data)} bytes"))
    write_index(args.out, entries, f"Compressed blocks in {os.path.basename(args.rom)}")
    print(f"{len(entries)} blocks written to {args.out}/ (open index.html to browse)")


def command_raw(args):
    rom = load_rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    palette = palette_for(rom, args, args.bpp)
    end = len(rom) if args.length is None else min(len(rom), args.start + args.length)
    entries = []
    # Split long regions into chunks so each PNG stays a reasonable size
    for chunk in range(args.start, end, args.chunk):
        data = rom[chunk:min(end, chunk + args.chunk)]
        surface = render_tiles(data, args.bpp, palette, args.width)
        if surface is None:
            continue
        name = f"raw_{chunk:07X}.png"
        save_scaled(surface, os.path.join(args.out, name), args.scale)
        entries.append((name, f"raw 0x{chunk:07X}-0x{chunk + len(data):07X}"))
    write_index(args.out, entries, f"Raw tiles of {os.path.basename(args.rom)}")
    print(f"{len(entries)} sheets written to {args.out}/ (open index.html to browse)")


def command_palettes(args):
    rom = load_rom(args.rom)
    offsets = find_palettes(rom, args.limit)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        surface = pygame.Surface((16 * 12, len(offsets) * 12))
        for row, offset in enumerate(offsets):
            for column, colour in enumerate(read_palette(rom, offset)):
                surface.fill(colour, (column * 12, row * 12, 12, 12))
        save_scaled(surface, os.path.join(args.out, "palettes.png"), 2)
        print(f"swatches in {args.out}/palettes.png (one row per offset below)")
    for offset in offsets:
        print(f"0x{offset:07X}")


def number(text):
    return int(text, 0)


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    commands = parser.add_subparsers(dest="command", required=True)

    def add_render_options(command):
        command.add_argument("--bpp", type=int, choices=(4, 8), default=4,
                             help="bits per pixel (sprites are usually 4)")
        command.add_argument("--width", type=int, default=16,
                             help="tiles per row in the sheet (default 16)")
        command.add_argument("--palette", type=number,
                             help="ROM offset of a palette (default: greyscale)")
        command.add_argument("--scale", type=int, default=2,
                             help="enlarge the PNGs (default 2)")

    scan = commands.add_parser("scan", help="find compressed blocks and render them")
    scan.add_argument("rom")
    scan.add_argument("out")
    add_render_options(scan)
    scan.add_argument("--min-size", type=number, default=0x200,
                      help="ignore blocks smaller than this (default 0x200)")
    scan.add_argument("--max-size", type=number, default=0x40000,
                      help="ignore blocks larger than this (default 0x40000)")
    scan.add_argument("--rle", action="store_true",
                      help="also look for run-length blocks (many false positives)")
    scan.add_argument("--save-data", action="store_true",
                      help="also write each decompressed block as .bin")
    scan.set_defaults(handler=command_scan)

    raw = commands.add_parser("raw", help="render an uncompressed ROM region")
    raw.add_argument("rom")
    raw.add_argument("out")
    add_render_options(raw)
    raw.add_argument("--start", type=number, default=0, help="first byte (default 0)")
    raw.add_argument("--length", type=number, help="bytes to render (default: to the end)")
    raw.add_argument("--chunk", type=number, default=0x8000,
                     help="bytes per PNG (default 0x8000)")
    raw.set_defaults(handler=command_raw)

    palettes = commands.add_parser("palettes", help="list likely palettes")
    palettes.add_argument("rom")
    palettes.add_argument("--limit", type=int, default=30)
    palettes.add_argument("--out", help="also draw the palettes into this folder")
    palettes.set_defaults(handler=command_palettes)
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    pygame.init()
    try:
        args.handler(args)
    finally:
        pygame.quit()


if __name__ == "__main__":
    main()
