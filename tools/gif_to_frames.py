#!/usr/bin/env python3
"""Turn an animated GIF into a grid of its frames (one PNG) the game can play
(pygame only loads a GIF's first frame). Needs Pillow (not the game).

    python3 tools/gif_to_frames.py Graphics/victory.gif Graphics/victory_frames.png [columns]

Prints the frame count and each frame's duration (ms): the game's player
(epic_screens.VictoryAnimation) uses them.
"""

import sys

from PIL import Image


def main():
    source, target = sys.argv[1], sys.argv[2]
    columns = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    gif = Image.open(source)
    frames, durations = [], []
    index = 0
    while True:
        try:
            gif.seek(index)
        except EOFError:
            break
        frames.append(gif.convert("RGBA").copy())
        durations.append(gif.info.get("duration", 100))
        index += 1
    width, height = frames[0].size
    rows = (len(frames) + columns - 1) // columns
    sheet = Image.new("RGBA", (width * columns, height * rows), (0, 0, 0, 0))
    for index, frame in enumerate(frames):
        sheet.paste(frame, ((index % columns) * width, (index // columns) * height))
    # A GIF has at most 256 colours: so does the PNG (much smaller)
    sheet = sheet.quantize(256, method=Image.Quantize.FASTOCTREE)
    sheet.save(target, optimize=True)
    print(f"{len(frames)} frames of {width}x{height}, {columns} a row, durations {sorted(set(durations))} ms")


if __name__ == "__main__":
    main()
