"""The cutscene of an "evolve" technique: the user turns into another
character with the help of a partner who comes out of nowhere.

    fusion   Goku and Vegeta (Potara earrings: Vegito), Goten and Kid Trunks
             (the Fusion Dance: Gotenks): the partner appears beside the
             user in a flash, they come together (glowing, with their own
             fusion frames when their sheets have some), a blinding light,
             and the fused warrior stands there. A fusion lasts its
             technique's lasts_s; then Defusion splits it again.
             With a "dance" (Gogeta's Fusion Dance), the two dance
             together instead (frames of both on one picture, from the
             technique's dance sheet), merge in light and the fused
             warrior steps out.
    absorb   Cell and an android: the android appears in front of him, his
             tail draws it in (it shrinks into him), he changes shape
             (his own transformation frames), a flash: his next form.

The user cannot be hurt meanwhile (its action is "evolve", see
Character.take_damage). The cutscene is an effect on the map (drawn over
the fighters), counted in 60 FPS frames like every effect.
"""

import pygame

from animation import Animator, AnimationDirection, load_sheet
from effects import Effect
from utils.config import Config

# Frames of each part, at 60 FPS
ARRIVE = 30
MEET = 54
FLASH = 40
FLASH_RADIUS = 70
# Where the partner appears: this far from the user, beside it (fusion) or
# in front of it (absorb)
FUSION_GAP = 56
ABSORB_GAP = 40
# Frames of a fusion dance, each shown this long
DANCE_TICKS = 7
# De-fusion, in 60 FPS frames: powering down, then the split
POWER_DOWN = 36
SPLIT = 48


def glow(radius, alpha):
    """A white light fading to its edge."""
    radius = max(2, radius)
    surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
    for ring in range(radius, 0, -max(1, radius // 8)):
        share = 1 - ring / radius
        pygame.draw.circle(surface, (255, 255, 235, int(alpha * (0.25 + 0.75 * share))), (radius, radius), ring)
    return surface


def compose(effect, layers, fallback_point):
    """Put layers [(surface, point, anchor)] on one picture: the effect's
    image and rect."""
    rects = [surface.get_rect(**{anchor: (round(point[0]), round(point[1]))}) for surface, point, anchor in layers]
    if not rects:
        effect.image = pygame.Surface((1, 1), pygame.SRCALPHA)
        effect.rect = effect.image.get_rect(center=fallback_point)
        return
    bounds = rects[0].unionall(rects[1:])
    image = pygame.Surface(bounds.size, pygame.SRCALPHA)
    for (surface, _, _), rect in zip(layers, rects):
        image.blit(surface, (rect.x - bounds.x, rect.y - bounds.y))
    effect.image = image
    effect.rect = bounds


def fusion_frames(animator, facing):
    """The glowing frames of a fighter merging, facing that way, or []."""
    flipped = facing == AnimationDirection.LEFT.value
    names = [f"Fuse {facing} {index}" for index in range(8)]
    return [animator.image_by_name(name, flipped) for name in names if animator.has_animation(name)]


class Evolution(Effect):
    def __init__(self, user, technique, on_done=None):
        super().__init__()
        self.user = user
        self.technique = technique
        self.style = technique.style or "fusion"
        self.on_done = on_done
        self.partner = Animator(technique.partner)
        self.became = False
        self.dance = self._dance_frames() if self.style == "fusion" else []
        # How long they take to come together (the dance's length)
        self.meet = len(self.dance) * DANCE_TICKS if self.dance else MEET
        # Who the user was (a fusion splits back into it)
        self.original = user.character_name
        # The partner faces the user, on its right if there is room
        user_x, user_y = user.rect.midbottom
        if self.style == "absorb":
            dx, dy = {"Right": (1, 0), "Left": (-1, 0), "Down": (0, 1), "Up": (0, -1)}.get(user.facing, (1, 0))
            self.start = (user_x + dx * ABSORB_GAP, user_y + dy * ABSORB_GAP * 0.6)
        else:
            self.start = (user_x + FUSION_GAP, user_y)
        self.partner_facing = "Left" if self.start[0] > user_x else "Right" if self.start[0] < user_x else "Up"
        user.facing = "Right" if self.start[0] > user_x else "Left" if self.start[0] < user_x else user.facing
        user.stop_block()
        frames = self._user_frames()
        # The user's frames play over the arrival and the meeting (or,
        # with a dance, the arrival)
        clock_speed = Config.CLOCK_LIMIT * len(frames) / (ARRIVE if self.dance else ARRIVE + MEET)
        user._play("evolve", frames, clock_speed, hold_ticks=10 ** 9)
        self.update_effect(())

    def _dance_frames(self):
        """The dance's pictures (both fighters on each), or [] without one
        (or when its sheet is missing)."""
        dance = getattr(self.technique, "dance", None)
        if not dance:
            return []
        try:
            sheet = load_sheet(dance["sheet"])
        except (pygame.error, FileNotFoundError, OSError):
            return []
        frames = []
        for x, y, width, height in dance["frames"]:
            image = pygame.Surface((width, height))
            image.blit(sheet, (0, 0), (x, y, width, height))
            image.set_colorkey(tuple(dance["background"]))
            frames.append(image)
        return frames

    def _user_frames(self):
        user = self.user
        if self.style == "absorb":
            frames = [user.frame_image(f"Transform {index}") for index in range(12)
                      if user.has_animation(f"Transform {index}")]
            if frames:
                return frames
        user.face_idle()
        glowing = fusion_frames(user.animator, user.facing) if self.style == "fusion" else []
        if glowing:
            # Standing while the partner arrives, glowing as they merge
            return [user.image] * 3 + glowing * 3
        return [user.image]

    def _became(self):
        """The user is the new character now; a fusion's clock starts."""
        self.became = True
        self.user.become(self.technique.becomes)
        lasts = getattr(self.technique, "lasts_s", None)
        if self.style == "fusion" and lasts:
            now = pygame.time.get_ticks()
            self.user.fusion = {"original": self.original, "partner": self.technique.partner,
                                "ends_ms": now + lasts * 1000, "total_ms": lasts * 1000,
                                "cooldown_s": getattr(self.technique, "cooldown_s", None) or 0}

    def finish(self):
        """End at once (the map changed): the user is the new character."""
        if not self.became:
            self._became()
        self.done = True
        self.user.action = None
        self.user.face_idle()
        if self.on_done is not None:
            self.on_done(self.user)

    @property
    def total(self):
        return ARRIVE + self.meet + FLASH

    def update_effect(self, targets):
        self.tick()
        t = self.ticks
        if self.dance and t == ARRIVE:
            # They dance together: one picture of both, where the user stands
            self.user._play("evolve", self.dance, Config.CLOCK_LIMIT * len(self.dance) / self.meet,
                            hold_ticks=10 ** 9)
        if t >= ARRIVE + self.meet and not self.became:
            # At the brightest of the flash, the user is someone else
            self._became()
            self.user.action = None
            self.user._play("evolve", [self.user.image], 10, hold_ticks=10 ** 9)
        if t >= self.total:
            self.done = True
            self.user.action = None
            self.user.face_idle()
            if self.on_done is not None:
                self.on_done(self.user)
            return
        self._compose(t)

    def _partner_frame(self, t):
        name = f"Walk {self.partner_facing}" if t >= ARRIVE else f"IDLE {self.partner_facing}"
        flipped = self.partner_facing == "Left"
        if t >= ARRIVE and self.style == "fusion":
            glowing = fusion_frames(self.partner, self.partner_facing)
            if glowing:
                return glowing[int(t // 6) % len(glowing)]
        if t >= ARRIVE:
            frames = self.partner.frames(name)
            if frames:
                return frames[int(t // 8) % len(frames)]
        return self.partner.image_by_name(f"IDLE {self.partner_facing}" if self.partner.has_animation(
            f"IDLE {self.partner_facing}") else "IDLE Down", flipped)

    def _compose(self, t):
        """The partner (fading in, coming over, shrinking into Cell) and
        the light, on one picture over the fighters."""
        user_ground = self.user.rect.midbottom
        layers = []  # (surface, midbottom or center, anchor)
        if t < ARRIVE + self.meet and not (self.dance and t >= ARRIVE):
            progress = 0.0 if t < ARRIVE else (t - ARRIVE) / self.meet
            ease = progress * progress * (3 - 2 * progress)
            x = self.start[0] + (user_ground[0] - self.start[0]) * ease
            y = self.start[1] + (user_ground[1] - self.start[1]) * ease
            frame = self._partner_frame(t)
            scale = 1.0 - 0.8 * ease if self.style == "absorb" else 1.0
            if scale != 1.0:
                frame = pygame.transform.scale(frame, (max(1, int(frame.get_width() * scale)),
                                                       max(1, int(frame.get_height() * scale))))
            frame = frame.copy()
            frame.set_alpha(int(255 * min(1.0, t / (ARRIVE * 0.6))))
            layers.append((frame, (x, y), "midbottom"))
            if t < ARRIVE:
                # The flash it comes out of
                radius = int(6 + 30 * (t / ARRIVE))
                layers.append((glow(radius, int(220 * (1 - t / ARRIVE))),
                               (self.start[0], self.start[1] - 16), "center"))
        if t >= ARRIVE + self.meet - MEET * 0.3:
            # The light where they meet, brightest at the change
            flash_t = t - (ARRIVE + self.meet - MEET * 0.3)
            span = MEET * 0.3 + FLASH
            peak = MEET * 0.3
            strength = flash_t / peak if flash_t < peak else max(0.0, 1 - (flash_t - peak) / (span - peak))
            radius = int(10 + FLASH_RADIUS * min(1.0, flash_t / peak))
            layers.append((glow(radius, int(250 * strength)),
                           (user_ground[0], user_ground[1] - self.user.rect.height / 2), "center"))
        compose(self, layers, user_ground)


class Defusion(Effect):
    """A fusion's time is up: the fused warrior powers down (its own
    frames, when its sheet has some), a flash, and the two split: the user
    is itself again (same share of HP), the partner leaves."""

    def __init__(self, user, on_done=None):
        super().__init__()
        self.user = user
        self.on_done = on_done
        fusion = user.fusion
        self.original = fusion["original"]
        self.partner = Animator(fusion["partner"])
        self.split = False
        user.stop_block()
        frames = [user.frame_image(f"Defuse {index}") for index in range(8) if user.has_animation(f"Defuse {index}")]
        if not frames:
            user.face_idle()
            frames = [user.image]
        user._play("evolve", frames, Config.CLOCK_LIMIT * len(frames) / POWER_DOWN, hold_ticks=10 ** 9)
        self.update_effect(())

    def _split(self):
        self.split = True
        cooldown = self.user.fusion.get("cooldown_s", 0)
        self.user.become(self.original)
        self.user.fusion = None
        if cooldown:
            # No fusing again right away
            now = pygame.time.get_ticks()
            self.user.fusion_cooldown = {"ends_ms": now + cooldown * 1000, "total_ms": cooldown * 1000}
        self.user.action = None
        self.user._play("evolve", [self.user.image], 10, hold_ticks=10 ** 9)

    def finish(self):
        """End at once (the map changed): split now."""
        if not self.split:
            self._split()
        self.done = True
        self.user.action = None
        self.user.face_idle()
        if self.on_done is not None:
            self.on_done(self.user)

    def update_effect(self, targets):
        self.tick()
        t = self.ticks
        if t >= POWER_DOWN and not self.split:
            self._split()
        if t >= POWER_DOWN + SPLIT:
            self.finish()
            return
        ground = self.user.rect.midbottom
        layers = []
        if t >= POWER_DOWN * 0.5:
            # The light it splits in, brightest at the split
            flash_t = t - POWER_DOWN * 0.5
            peak = POWER_DOWN * 0.5
            strength = flash_t / peak if flash_t < peak else max(0.0, 1 - (flash_t - peak) / SPLIT)
            radius = int(10 + FLASH_RADIUS * 0.8 * min(1.0, flash_t / peak))
            layers.append((glow(radius, int(240 * strength)), (ground[0], ground[1] - self.user.rect.height / 2),
                           "center"))
        if self.split:
            # The partner steps out to the side and fades away
            progress = (t - POWER_DOWN) / SPLIT
            frame = self.partner.image_by_name("IDLE Down").copy()
            frame.set_alpha(int(255 * max(0.0, 1 - progress)))
            layers.insert(0, (frame, (ground[0] + FUSION_GAP * min(1.0, progress * 1.6), ground[1]), "midbottom"))
        compose(self, layers, ground)

