"""What an Epic Fight shows besides the fight: its versus card before it
starts (the heroes against the boss, the title, a few lines), and the wave
banner when more enemies arrive."""

import pygame

from portraits import portrait
from roster import display_name
from taps import tap_position


class EpicIntro:
    """The versus card: shown over the frozen fight until a key, a button
    or a tap."""

    DISMISS_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE, pygame.K_j, pygame.K_z)
    # Not before this long (a key still held from the menu must not skip it)
    MIN_MS = 400

    def __init__(self, screen_size, fight, online_side=None):
        self.fight = fight
        # Online: which side this player plays (0 the heroes, 1 the boss)
        self.online_side = online_side
        self.shown_at = pygame.time.get_ticks()
        self.resize(screen_size)

    def resize(self, screen_size):
        self.screen_size = screen_size
        width, height = screen_size
        shortest = min(screen_size)
        self.panel = pygame.Rect(0, 0, min(width - 32, max(420, int(width * 0.8))),
                                 min(height - 32, max(300, int(height * 0.78))))
        self.panel.center = (width // 2, height // 2)
        self.title_font = pygame.font.Font(None, max(34, int(shortest * 0.075)))
        self.text_font = pygame.font.Font(None, max(22, int(shortest * 0.04)))
        self.small_font = pygame.font.Font(None, max(18, int(shortest * 0.032)))
        self.versus_font = pygame.font.Font(None, max(40, int(shortest * 0.1)))
        self.portrait_size = max(56, int(shortest * 0.17))
        self.shade = pygame.Surface(screen_size, pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 170))

    def process(self, events):
        """True once the player wants to fight."""
        if pygame.time.get_ticks() - self.shown_at < self.MIN_MS:
            return False
        for event in events:
            if event.type == pygame.KEYDOWN and event.key in self.DISMISS_KEYS:
                return True
            if tap_position(event, self.screen_size) is not None:
                return True
        return False

    def _portrait(self, name):
        size = self.portrait_size
        face = portrait(name)
        frame = pygame.Surface((size, size), pygame.SRCALPHA)
        if face is not None:
            frame.blit(pygame.transform.scale(face, (size, size)), (0, 0))
        else:
            frame.fill((60, 60, 80))
        return frame

    def draw(self, screen):
        fight = self.fight
        screen.blit(self.shade, (0, 0))
        pygame.draw.rect(screen, (20, 22, 38), self.panel, border_radius=16)
        pygame.draw.rect(screen, (255, 205, 60), self.panel, 3, border_radius=16)
        top = self.panel.top + 14
        title = self.title_font.render(fight.title, True, (255, 220, 90))
        screen.blit(title, title.get_rect(midtop=(self.panel.centerx, top)))
        top += title.get_height() + 2
        subtitle = self.text_font.render(fight.subtitle, True, (220, 220, 235))
        screen.blit(subtitle, subtitle.get_rect(midtop=(self.panel.centerx, top)))
        top += subtitle.get_height() + 12

        # The heroes on the left, the boss (and its first wave) on the right
        size = self.portrait_size
        hero, _, allies = fight.side(0)
        boss = fight.face
        left = self._portrait(hero)
        right = self._portrait(boss)
        left_rect = left.get_rect(topright=(self.panel.centerx - size // 2, top))
        right_rect = right.get_rect(topleft=(self.panel.centerx + size // 2, top))
        screen.blit(left, left_rect)
        screen.blit(right, right_rect)
        pygame.draw.rect(screen, (120, 195, 255), left_rect, 3)
        pygame.draw.rect(screen, (235, 90, 80), right_rect, 3)
        versus = self.versus_font.render("VS", True, (255, 255, 255))
        screen.blit(versus, versus.get_rect(center=(self.panel.centerx, left_rect.centery)))
        heroes = " + ".join(display_name(name) for name in (hero, *allies))
        enemies = sum(len(wave) for wave in fight.waves)
        villains = display_name(boss) + (f" + {enemies - 1} more" if enemies > 1 else "")
        for text, rect, color in ((heroes, left_rect, (120, 195, 255)), (villains, right_rect, (235, 90, 80))):
            label = self.small_font.render(text, True, color)
            screen.blit(label, label.get_rect(midtop=(rect.centerx, rect.bottom + 4)))
        top = left_rect.bottom + self.small_font.get_height() + 16

        # What they say
        for speaker, line in fight.intro:
            if top > self.panel.bottom - 60:
                break
            name = self.text_font.render(f"{display_name(speaker)}:", True, (255, 220, 90))
            screen.blit(name, (self.panel.left + 24, top))
            for row in self._wrap(line, self.panel.width - 48 - name.get_width() - 8):
                text = self.text_font.render(row, True, (240, 240, 245))
                screen.blit(text, (self.panel.left + 24 + name.get_width() + 8, top))
                top += text.get_height() + 2
            top += 6

        # The quest
        if fight.quest is not None and self.online_side is None:
            for line in quest_lines(fight):
                if top > self.panel.bottom - 50:
                    break
                text = self.text_font.render(f"Quest: {line}", True, (140, 230, 140))
                screen.blit(text, text.get_rect(midtop=(self.panel.centerx, top)))
                top += text.get_height() + 2

        if self.online_side is not None:
            side = "the heroes" if self.online_side == 0 else display_name(boss)
            note = self.small_font.render(f"Online: you play {side}", True, (160, 230, 160))
            screen.blit(note, note.get_rect(midbottom=(self.panel.centerx, self.panel.bottom - 34)))
        hint = self.small_font.render("Press Enter, A or tap to fight!", True, (200, 200, 210))
        screen.blit(hint, hint.get_rect(midbottom=(self.panel.centerx, self.panel.bottom - 12)))

    def _wrap(self, text, width):
        rows, row = [], ""
        for word in text.split():
            candidate = f"{row} {word}".strip()
            if self.text_font.size(candidate)[0] > width and row:
                rows.append(row)
                row = word
            else:
                row = candidate
        if row:
            rows.append(row)
        return rows


class WaveBanner:
    """"Wave 2!" for a moment when more enemies arrive."""

    SHOW_MS = 1800

    def __init__(self, screen_size, number, total):
        self.text = f"Wave {number} of {total}!"
        self.until = pygame.time.get_ticks() + self.SHOW_MS
        self.font = pygame.font.Font(None, max(40, int(min(screen_size) * 0.09)))
        self.screen_size = screen_size

    @property
    def done(self):
        return pygame.time.get_ticks() >= self.until

    def draw(self, screen):
        label = self.font.render(self.text, True, (255, 220, 90))
        shadow = self.font.render(self.text, True, (20, 20, 30))
        center = (self.screen_size[0] // 2, int(self.screen_size[1] * 0.3))
        screen.blit(shadow, shadow.get_rect(center=(center[0] + 3, center[1] + 3)))
        screen.blit(label, label.get_rect(center=center))


class VictoryAnimation:
    """Graphics/victory.gif, played: its frames are a grid in
    Graphics/victory_frames.png (tools/gif_to_frames.py: pygame only loads
    a GIF's first frame)."""

    PATH = "Graphics/victory_frames.png"
    FRAME_SIZE = (498, 286)
    COLUMNS = 6
    COUNT = 24
    FRAME_MS = 50
    _frames = None

    @classmethod
    def frames(cls):
        """Its frames, or [] when the picture is missing."""
        if cls._frames is None:
            import os
            from utils.config import Config
            try:
                sheet = pygame.image.load(os.path.join(Config.ROOT_DIR, cls.PATH))
            except (pygame.error, FileNotFoundError, OSError):
                cls._frames = []
                return cls._frames
            width, height = cls.FRAME_SIZE
            cls._frames = [sheet.subsurface(((index % cls.COLUMNS) * width, (index // cls.COLUMNS) * height,
                                              width, height)).copy() for index in range(cls.COUNT)]
        return cls._frames

    def __init__(self):
        self.started = pygame.time.get_ticks()
        self._scaled = {}

    def frame(self, width=None):
        """The frame to show now (scaled to width, kept for reuse), or None."""
        frames = self.frames()
        if not frames:
            return None
        index = (pygame.time.get_ticks() - self.started) // self.FRAME_MS % len(frames)
        if width is None:
            return frames[index]
        key = (index, width)
        if key not in self._scaled:
            height = round(width * self.FRAME_SIZE[1] / self.FRAME_SIZE[0])
            # Smooth scaling needs 32 bits (the frames have a palette)
            full = pygame.Surface(frames[index].get_size(), pygame.SRCALPHA)
            full.blit(frames[index], (0, 0))
            self._scaled[key] = pygame.transform.smoothscale(full, (width, height))
        return self._scaled[key]


class AllClearedScreen:
    """Every Epic Fight won: the victory animation, until a key or a tap."""

    MIN_MS = 1200

    def __init__(self, screen_size):
        self.animation = VictoryAnimation()
        self.shown_at = pygame.time.get_ticks()
        self.resize(screen_size)

    def resize(self, screen_size):
        self.screen_size = screen_size
        shortest = min(screen_size)
        self.title_font = pygame.font.Font(None, max(40, int(shortest * 0.09)))
        self.text_font = pygame.font.Font(None, max(22, int(shortest * 0.045)))
        self.shade = pygame.Surface(screen_size, pygame.SRCALPHA)
        self.shade.fill((0, 0, 0, 200))

    def process(self, events):
        """True once the player moves on."""
        if pygame.time.get_ticks() - self.shown_at < self.MIN_MS:
            return False
        for event in events:
            if event.type == pygame.KEYDOWN or tap_position(event, self.screen_size) is not None:
                return True
        return False

    def draw(self, screen):
        width, height = self.screen_size
        screen.blit(self.shade, (0, 0))
        title = self.title_font.render("All Epic Fights completed!", True, (255, 220, 90))
        screen.blit(title, title.get_rect(midtop=(width // 2, int(height * 0.06))))
        picture = self.animation.frame(min(width - 40, int((height * 0.62) * 498 / 286)))
        top = int(height * 0.06) + title.get_height() + 12
        if picture is not None:
            rect = picture.get_rect(midtop=(width // 2, top))
            screen.blit(picture, rect)
            pygame.draw.rect(screen, (255, 205, 60), rect.inflate(6, 6), 3, border_radius=6)
            top = rect.bottom + 12
        for line, colour in (("Congratulations, you saved the world!", (240, 240, 245)),
                             ("Press any key or tap to continue", (180, 185, 200))):
            text = self.text_font.render(line, True, colour)
            screen.blit(text, text.get_rect(midtop=(width // 2, top)))
            top += text.get_height() + 6


def quest_lines(fight):
    """The fight's quest in words, its technique by its own name."""
    quest = fight.quest
    if quest is None:
        return []
    name = None
    if quest.finisher:
        import json
        import os
        from utils.config import Config
        for character in {fight.hero, *fight.allies}:
            path = os.path.join(Config.ROOT_DIR, "Config", "characters", character, "specials.json")
            try:
                with open(path, encoding="utf-8") as file:
                    techniques = json.load(file).get("techniques", [])
            except (OSError, ValueError):
                continue
            name = next((t["name"] for t in techniques if t.get("id") == quest.finisher), name)
    return quest.lines(fight.boss, name)


class QuestPanel:
    """An Epic Fight's quest at the top of the screen while it is fought:
    what to do, the time left to hold out, who must not fall."""

    def __init__(self, screen_size, fight):
        self.fight = fight
        self.lines = quest_lines(fight)
        self.font = pygame.font.Font(None, max(20, int(min(screen_size) * 0.036)))
        self.screen_size = screen_size

    def draw(self, screen, elapsed_ms, fighters=()):
        quest = self.fight.quest
        if quest is None:
            return
        rows = []
        for line in self.lines:
            colour = (235, 235, 240)
            if quest.survive and line.startswith("Survive"):
                left = max(0, quest.survive - elapsed_ms / 1000)
                line = f"Survive: {int(left) // 60}:{int(left) % 60:02d}"
                colour = (255, 220, 90) if left > 10 else (255, 120, 100)
            for name in quest.protect:
                if line.startswith(display_name(name)):
                    down = any(f.character_name == name and f.hp <= 0 for f in fighters)
                    colour = (255, 110, 100) if down else (140, 230, 140)
            rows.append(self.font.render(line, True, colour))
        width = max(row.get_width() for row in rows) + 24
        height = sum(row.get_height() + 2 for row in rows) + 12
        panel = pygame.Rect(0, 0, width, height)
        panel.midtop = (self.screen_size[0] // 2, 8)
        plate = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(plate, (12, 14, 24, 170), plate.get_rect(), border_radius=8)
        screen.blit(plate, panel.topleft)
        top = panel.top + 6
        for row in rows:
            screen.blit(row, row.get_rect(midtop=(panel.centerx, top)))
            top += row.get_height() + 2
