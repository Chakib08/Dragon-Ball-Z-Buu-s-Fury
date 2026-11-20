"""The cutscene of an "evolve" technique: the user turns into another
character with the help of a partner who comes out of nowhere.

    fusion   Goku and Vegeta, Potara earrings: the partner appears beside
             the user in a flash, they fly into each other, a blinding light,
             and Vegito stands there.
    absorb   Cell and an android: the android appears in front of him, his
             tail draws it in (it shrinks into him), he changes shape
             (his own transformation frames), a flash: his next form.

The user cannot be hurt meanwhile (its action is "evolve", see
Character.take_damage). The cutscene is an effect on the map (drawn over
the fighters), counted in 60 FPS frames like every effect.
"""

import pygame

from animation import Animator
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


class Evolution(Effect):
    def __init__(self, user, technique, on_done=None):
        super().__init__()
        self.user = user
        self.technique = technique
        self.style = technique.style or "fusion"
        self.on_done = on_done
        self.partner = Animator(technique.partner)
        self.became = False
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
        # The user's frames play over the arrival and the meeting
        clock_speed = Config.CLOCK_LIMIT * len(frames) / (ARRIVE + MEET)
        user._play("evolve", frames, clock_speed, hold_ticks=10 ** 9)
        self.update_effect(())

    def _user_frames(self):
        user = self.user
        if self.style == "absorb":
            frames = [user.frame_image(f"Transform {index}") for index in range(12)
                      if user.has_animation(f"Transform {index}")]
            if frames:
                return frames
        user.face_idle()
        return [user.image]

    def finish(self):
        """End at once (the map changed): the user is the new character."""
        if not self.became:
            self.became = True
            self.user.become(self.technique.becomes)
        self.done = True
        self.user.action = None
        self.user.face_idle()
        if self.on_done is not None:
            self.on_done(self.user)

    @property
    def total(self):
        return ARRIVE + MEET + FLASH

    def update_effect(self, targets):
        self.tick()
        t = self.ticks
        if t >= ARRIVE + MEET and not self.became:
            # At the brightest of the flash, the user is someone else
            self.became = True
            self.user.become(self.technique.becomes)
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
        if t < ARRIVE + MEET:
            progress = 0.0 if t < ARRIVE else (t - ARRIVE) / MEET
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
                layers.append((self._glow(radius, int(220 * (1 - t / ARRIVE))),
                               (self.start[0], self.start[1] - 16), "center"))
        if t >= ARRIVE + MEET * 0.7:
            # The light where they meet, brightest at the change
            flash_t = t - (ARRIVE + MEET * 0.7)
            span = MEET * 0.3 + FLASH
            peak = MEET * 0.3
            strength = flash_t / peak if flash_t < peak else max(0.0, 1 - (flash_t - peak) / (span - peak))
            radius = int(10 + FLASH_RADIUS * min(1.0, flash_t / peak))
            layers.append((self._glow(radius, int(250 * strength)),
                           (user_ground[0], user_ground[1] - self.user.rect.height / 2), "center"))
        # One picture holding every layer
        rects = []
        for surface, point, anchor in layers:
            rect = surface.get_rect(**{anchor: (round(point[0]), round(point[1]))})
            rects.append(rect)
        if not rects:
            self.image = pygame.Surface((1, 1), pygame.SRCALPHA)
            self.rect = self.image.get_rect(center=user_ground)
            return
        bounds = rects[0].unionall(rects[1:])
        image = pygame.Surface(bounds.size, pygame.SRCALPHA)
        for (surface, _, _), rect in zip(layers, rects):
            image.blit(surface, (rect.x - bounds.x, rect.y - bounds.y))
        self.image = image
        self.rect = bounds

    @staticmethod
    def _glow(radius, alpha):
        """A white light fading to its edge."""
        radius = max(2, radius)
        surface = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
        for ring in range(radius, 0, -max(1, radius // 8)):
            share = 1 - ring / radius
            pygame.draw.circle(surface, (255, 255, 235, int(alpha * (0.25 + 0.75 * share))), (radius, radius), ring)
        return surface
