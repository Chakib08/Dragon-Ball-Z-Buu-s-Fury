"""Taps and clicks, counted once.

On Android (and other touch screens) SDL reports a touch twice: as a
FINGERDOWN event, and as a MOUSEBUTTONDOWN copy for programs that only know
the mouse. A button that toggles something (pick a card / unpick it) would
take both, and undo the tap at once; a button that changes screen would let
the copy press whatever sits at the same spot on the next screen.

pygame 2 marks the copy with touch=True: it is skipped.
"""

import pygame


def tap_position(event, screen_size):
    """Where a tap or a left click happened, in screen pixels; None for any
    other event, and for the mouse copy of a touch."""
    if event.type == pygame.FINGERDOWN:
        return event.x * screen_size[0], event.y * screen_size[1]
    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and not getattr(event, "touch", False):
        return event.pos
    return None
