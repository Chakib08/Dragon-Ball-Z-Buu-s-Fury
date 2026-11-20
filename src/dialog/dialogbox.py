import pygame

from pathmanager import PathManager
import portraits

# Layout designed for a 1200x1000 screen
BOX_SIZE = (700, 300)
PORTRAIT_SIZE = (300, 300)
BOTTOM_MARGIN = 50

WHITE = (255, 255, 255)
FONT_SIZE = 40

# TODO: Remove magic numbers and retreive the from a YAML or JSON config file

class DialogBox:
    def __init__(self, screen_size=(1200, 1000)) -> None:
        self.texts = ["KAKAROT !!!", "I want my revenge !!"]
        self.text_idx = 0
        self.letter_idx = 0
        self.isBoxOpened = False
        self.resize(screen_size)

    def resize(self, screen_size):
        """Lay the box out for this screen size (what it says is kept)."""
        total_width = BOX_SIZE[0] + PORTRAIT_SIZE[0]
        scale = min(1, screen_size[0] / (total_width + 100), screen_size[1] / 1000)
        box_size = (round(BOX_SIZE[0] * scale), round(BOX_SIZE[1] * scale))
        portrait_size = (round(PORTRAIT_SIZE[0] * scale), round(PORTRAIT_SIZE[1] * scale))
        self.scale = scale
        self.box_width = box_size[0]
        self.x = (screen_size[0] - box_size[0] - portrait_size[0]) // 2
        self.y = screen_size[1] - box_size[1] - round(BOTTOM_MARGIN * scale)
        self.box = self.get_image(PathManager.dialog_file("dialogbox.png"), (68, 140, 203), (6, 16, 160, 64), (160,64))
        self.box = pygame.transform.scale(self.box, box_size)
        # Vegeta's angry face, from the portraits sheet setup.sh downloads
        # (a plain frame if it is missing)
        sheet = portraits.sheet("bf")
        self.portrait = pygame.Surface((64, 64))
        if sheet is not None:
            self.portrait.blit(sheet, (0, 0), (171, 607, 64, 64))
            self.portrait.set_colorkey((255, 174, 201))
        self.portrait = pygame.transform.scale(self.portrait, portrait_size)
        self.font = pygame.font.Font(PathManager.dialog_file("dialog_font.ttf"), max(12, round(FONT_SIZE * scale)))
        
    def render(self, screen):
        if self.isBoxOpened:
            # Typewriter effect: one more letter per frame
            self.letter_idx = min(self.letter_idx + 1, len(self.texts[self.text_idx]))
            screen.blit(self.box, (self.x, self.y))
            text = self.font.render(self.texts[self.text_idx][0:self.letter_idx], False, WHITE)
            screen.blit(text, (self.x + round(30 * self.scale), self.y + round(20 * self.scale)))
            screen.blit(self.portrait, (self.x + self.box_width, self.y))
    
    def get_image(self, img_path: str, bg: tuple, pos: tuple, size: tuple) -> pygame.Surface:
        full_img = pygame.image.load(img_path)
        img = pygame.Surface(size)
        img.blit(full_img, (0, 0), pos)
        img.set_colorkey(bg)
        return img
    
    def next_text(self):
        self.text_idx += 1
        self.letter_idx = 0
        
        if(self.text_idx >= len(self.texts)):
            self.isBoxOpened = False
    
    def open(self, dialog_texts=()):
        if self.isBoxOpened:
            self.next_text()
        elif dialog_texts:  # nothing to say: stay closed (no line to show)
            self.isBoxOpened = True
            self.text_idx = 0
            self.texts = dialog_texts