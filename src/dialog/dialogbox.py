import pygame

from pathmanager import PathManager

X_POS = 50
Y_POS = 650

WHITE = (255, 255, 255)
FRONT_SIZE = 40

class DialogBox:
    def __init__(self) -> None:
        self.box = self.get_image(PathManager.dialogFile("dialogbox.png"), (68, 140, 203), (6, 16, 160, 64), (160,64))
        self.box = pygame.transform.scale(self.box, (700, 300))
        self.portrait = self.get_image(PathManager.dialogFile("portraits.png"), (255, 174, 201), (171, 607, 64, 64), (64, 64))
        self.portrait = pygame.transform.scale(self.portrait, (300, 300))
        self.texts = ["KAKAROT !!!", "J'ai une envie préssante", "d'aller aux toilette !!"]
        self.text_idx = 0
        self.letter_idx = 0
        self.font = pygame.font.Font(PathManager.dialogFile("dialog_font.ttf"), FRONT_SIZE)
        self.isBoxOpened = False
        
    def render(self, screen):
        if self.isBoxOpened:
            self.letter_idx += 1
            if self.letter_idx >= len(self.texts[self.text_idx]):
                self.letter_idx = self.letter_idx
            screen.blit(self.box, (X_POS, Y_POS))
            text = self.font.render(self.texts[self.text_idx][0:self.letter_idx], False, WHITE)
            screen.blit(text, (X_POS + 30, Y_POS + 20))
            screen.blit(self.portrait, (X_POS + 700, Y_POS))
    
    def get_image(self, img_path: str, bg : tuple, pos : tuple, size :tuple) -> pygame.Surface:
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
    
    def open(self):
        if self.isBoxOpened:
            self.next_text()
        else:
            self.isBoxOpened = True
            self.text_idx = 0