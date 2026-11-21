#!/usr/bin/env python3
"""Make the Android launcher icon from Graphics/android_icon.png.

The source picture is a rounded square on a black background. The black
around it (reached from the corners, so dark outlines inside the picture
are kept) becomes transparent, and the result is scaled to 512x512, the
size Android uses for the store and the largest launcher icons:

    python3 tools/make_android_icon.py   # writes Graphics/android/icon.png

buildozer.spec points icon.filename at the result.
"""

import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCE = os.path.join(ROOT, "Graphics", "android_icon.png")
TARGET = os.path.join(ROOT, "Graphics", "android", "icon.png")
SIZE = 512
# A pixel this dark (every channel) counts as the black background
BLACK = 24


def clear_corners(image):
    """Make the black reached from the four corners transparent."""
    width, height = image.get_size()
    seen = bytearray(width * height)
    stack = [(0, 0), (width - 1, 0), (0, height - 1), (width - 1, height - 1)]
    transparent = (0, 0, 0, 0)
    while stack:
        x, y = stack.pop()
        index = y * width + x
        if seen[index]:
            continue
        seen[index] = 1
        r, g, b, _ = image.get_at((x, y))
        if max(r, g, b) > BLACK:
            continue
        image.set_at((x, y), transparent)
        if x > 0:
            stack.append((x - 1, y))
        if x < width - 1:
            stack.append((x + 1, y))
        if y > 0:
            stack.append((x, y - 1))
        if y < height - 1:
            stack.append((x, y + 1))


def main():
    pygame.init()
    pygame.display.set_mode((1, 1))
    image = pygame.image.load(SOURCE).convert_alpha()
    clear_corners(image)
    icon = pygame.transform.smoothscale(image, (SIZE, SIZE))
    os.makedirs(os.path.dirname(TARGET), exist_ok=True)
    pygame.image.save(icon, TARGET)
    print(f"wrote {os.path.relpath(TARGET, ROOT)} ({SIZE}x{SIZE})")


if __name__ == "__main__":
    sys.exit(main())
