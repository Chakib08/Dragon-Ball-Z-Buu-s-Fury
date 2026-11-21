"""Sound effects and voices: punches, blasts, beams, auras, fusions, the
menu's cursor...

The sounds are WAV files in Sounds/sfx/ (setup.sh installs them from the
dbz-assets repository): Buu's Fury, Legacy of Goku 2 and Dragon Ball GT
Transformation sounds. A name is a group: play("melee") picks one of
melee-1.wav, melee-2.wav... at random, so repeated hits do not all sound
the same.

Everything here is optional: without a sound device (tests, a server) or
without the files, play() does nothing.
"""

import os
import random

import pygame

from utils.config import Config

VOLUME = 0.45
# The same sound at most this often (a crowd hitting at once would be noise)
MIN_GAP_MS = 45
# Some sounds are quieter or louder than the others
LEVELS = {"miss": 0.5, "cursor": 0.6, "aura": 0.8, "explode": 0.8, "kaboom": 0.8, "ko": 0.9}
# Characters' voices (Dragon Ball GT Transformation clips): who shouts
VOICES = {
    "goku": "adultgoku", "goku_log2": "adultgoku", "goku_end_of_z": "adultgoku", "goku_black": "adultgoku",
    "vegeta": "vegeta", "vegeta_log2": "vegeta",
    "trunks": "trunks", "trunks_future": "trunks",
    "piccolo": "piccolo",
    "goten": "kidgoku", "kid_trunks": "kidgoku", "gotenks": "kidgoku",
    "gohan_teen": "kidgoku",
    # The fused warriors speak with both voices
    "vegito": ("adultgoku", "vegeta"), "gogeta": ("adultgoku", "vegeta"),
}

# Its own random picks: sounds never change the fights' random numbers
_random = random.Random()
_groups = None
_sounds = {}
_last_played = {}


def _folder():
    return os.path.join(Config.ROOT_DIR, "Sounds", "sfx")


def _scan():
    """{group: [file names]} of Sounds/sfx: "melee-1.wav" is in "melee"
    (and in "melee-1")."""
    global _groups
    if _groups is None:
        _groups = {}
        try:
            names = sorted(name[:-4] for name in os.listdir(_folder()) if name.endswith(".wav"))
        except OSError:
            names = []
        for name in names:
            _groups.setdefault(name, []).append(name)
            stem, _, number = name.rpartition("-")
            if stem and number.isdigit():
                _groups.setdefault(stem, []).append(name)
    return _groups


def available(name):
    return bool(_scan().get(name))


def _sound(name):
    sound = _sounds.get(name)
    if sound is None:
        sound = _sounds[name] = pygame.mixer.Sound(os.path.join(_folder(), f"{name}.wav"))
    return sound


def play(name, volume=1.0):
    """Play a sound of the group name; returns the file played, or None
    (no sound device, no such file, or played a moment ago)."""
    if not pygame.mixer.get_init():
        return None
    choices = _scan().get(name)
    if not choices:
        return None
    now = pygame.time.get_ticks()
    last = _last_played.get(name)
    if last is not None and now - last < MIN_GAP_MS:
        return None
    _last_played[name] = now
    chosen = _random.choice(choices)
    try:
        sound = _sound(chosen)
        sound.set_volume(max(0.0, min(1.0, VOLUME * LEVELS.get(name, 1.0) * volume)))
        sound.play()
    except pygame.error:
        return None
    return chosen


def voice_of(character_name):
    """The voice group of a character ("voice-vegeta"), or None."""
    voice = VOICES.get(character_name)
    if voice is None:
        return None
    if isinstance(voice, tuple):
        voice = _random.choice(voice)
    return f"voice-{voice}"


def shout(character_name, volume=1.0):
    """The character's voice (a shout), when it has one."""
    voice = voice_of(character_name)
    return play(voice, volume) if voice else None


def reset():
    """Forget the files found (tests, after installing sounds)."""
    global _groups
    _groups = None
    _sounds.clear()
    _last_played.clear()
