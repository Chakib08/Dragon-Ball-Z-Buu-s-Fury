"""The frame clock: how much game time the current frame stands for.

Speeds and animation clocks in the game are tuned per frame at 60 frames a
second. A device that runs slower (a phone at 40 FPS) or faster must still
play at the same speed, so each frame scales those steps by ticks(): 1.0 at
60 FPS, 1.5 at 40 FPS, 0.5 at 120 FPS. Cooldowns and timers already use
milliseconds (pygame.time.get_ticks) and need nothing.

The game loop calls advance() once per frame with the time it took. Until it
does (tests, tools), ticks() is 1.0: one frame is one 60 FPS frame.
"""

REFERENCE_FPS = 60
# A long stall (loading a map, the app in the background) counts as at most
# this many frames, so nothing jumps through a wall or across the screen
MAX_TICKS = 3.0

_ticks = 1.0


def ticks():
    return _ticks


def advance(elapsed_ms):
    """The frame that starts took elapsed_ms since the previous one."""
    global _ticks
    _ticks = min(MAX_TICKS, max(0.0, elapsed_ms * REFERENCE_FPS / 1000.0))


def reset():
    global _ticks
    _ticks = 1.0


def smoothing(share_per_frame):
    """A "cover this share of the gap each frame" factor for this frame."""
    return 1 - (1 - share_per_frame) ** _ticks
