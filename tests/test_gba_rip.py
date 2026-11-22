import os
import sys
import tempfile
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import pygame

import gba_rip


def lz77_compress(data):
    """Small, slow LZ77 (BIOS 0x10) encoder, only to build test ROMs."""
    out = bytearray([0x10]) + len(data).to_bytes(3, "little")
    pos = 0
    while pos < len(data):
        flags_at = len(out)
        out.append(0)
        for bit in range(8):
            if pos >= len(data):
                break
            best_length, best_distance = 0, 0
            for distance in range(1, min(pos, 0x1000) + 1):
                length = 0
                while (length < 18 and pos + length < len(data)
                       and data[pos + length] == data[pos + length - distance]):
                    length += 1
                if length > best_length:
                    best_length, best_distance = length, distance
            if best_length >= 3:
                out[flags_at] |= 0x80 >> bit
                encoded = ((best_length - 3) << 12) | (best_distance - 1)
                out += encoded.to_bytes(2, "big")
                pos += best_length
            else:
                out.append(data[pos])
                pos += 1
    while len(out) % 4:
        out.append(0)
    return bytes(out)


def fake_rom(*blocks):
    """A minimal GBA ROM: valid header, then the given blocks 4-byte aligned."""
    header = bytearray(0xC0)
    header[0xA0:0xAC] = b"TESTGAME".ljust(12, b"\0")
    header[0xAC:0xB0] = b"ATST"
    header[0xB2] = 0x96
    rom = bytearray(header)
    offsets = []
    for block in blocks:
        while len(rom) % 4:
            rom.append(0xFF)
        offsets.append(len(rom))
        rom += block
    rom += b"\xFF" * 64
    return bytes(rom), offsets


def checkerboard_tiles(count):
    """4bpp tiles: colour index 1 and 2 in a checkerboard, a different
    pattern per tile so the data is not trivially repetitive."""
    data = bytearray()
    for tile in range(count):
        for y in range(8):
            for x in range(0, 8, 2):
                a = 1 + (x + y + tile) % 2
                b = 1 + (x + 1 + y + tile) % 2
                data.append(a | (b << 4))
    return bytes(data)


class GbaRipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_lz77_round_trip(self):
        data = checkerboard_tiles(32) + bytes(range(256))
        compressed = lz77_compress(data)
        decoded, used = gba_rip.lz77_decompress(compressed, 0, 0x10000)
        self.assertEqual(decoded, data)
        self.assertLessEqual(used, len(compressed))

    def test_rle(self):
        stream = bytes([0x30]) + (12).to_bytes(3, "little") + bytes([0x87, 0xAA, 0x01, 1, 2])
        decoded, _ = gba_rip.rle_decompress(stream, 0, 100)
        self.assertEqual(decoded, b"\xAA" * 10 + b"\x01\x02")

    def test_scan_finds_compressed_graphics_and_skips_noise(self):
        tiles = checkerboard_tiles(64)
        noise = bytes([0x10, 0xFF, 0xFF, 0x7F]) + os.urandom(64)
        rom, offsets = fake_rom(noise, lz77_compress(tiles))
        found = list(gba_rip.find_compressed(rom, 0x100, 0x40000))
        self.assertEqual([(offset, kind) for offset, kind, _ in found], [(offsets[1], "lz77")])
        self.assertEqual(found[0][2], tiles)

    def test_tiles_render_with_the_palette(self):
        palette = [(0, 0, 0), (255, 0, 0), (0, 0, 255)] + [(0, 0, 0)] * 13
        surface = gba_rip.render_tiles(checkerboard_tiles(4), 4, palette, tiles_per_row=2)
        self.assertEqual(surface.get_size(), (16, 16))
        self.assertEqual(surface.get_at((0, 0))[:3], (255, 0, 0))
        self.assertEqual(surface.get_at((1, 0))[:3], (0, 0, 255))

    def test_palette_reading_and_detection(self):
        values = [0x0000, 0x001F, 0x03E0, 0x7C00] + [0x0421 * (i + 1) for i in range(12)]
        raw = b"".join(value.to_bytes(2, "little") for value in values)
        rom, offsets = fake_rom(raw)
        colours = gba_rip.read_palette(rom, offsets[0])
        self.assertEqual(colours[1], (255, 0, 0))
        self.assertEqual(colours[3], (0, 0, 255))
        self.assertIn(offsets[0], gba_rip.find_palettes(rom, limit=5))

    def test_scan_command_writes_sheets_and_an_index(self):
        rom, offsets = fake_rom(lz77_compress(checkerboard_tiles(64)))
        with tempfile.TemporaryDirectory() as folder:
            rom_path = os.path.join(folder, "test.gba")
            with open(rom_path, "wb") as file:
                file.write(rom)
            out = os.path.join(folder, "rips")
            gba_rip.main(["scan", rom_path, out, "--min-size", "0x100"])
            sheet = os.path.join(out, f"lz77_{offsets[0]:07X}.png")
            self.assertTrue(os.path.exists(sheet))
            self.assertIn(os.path.basename(sheet), open(os.path.join(out, "index.html")).read())
            pygame.init()
            self.assertEqual(pygame.image.load(sheet).get_size(), (16 * 8 * 2, 4 * 8 * 2))


if __name__ == "__main__":
    unittest.main()
