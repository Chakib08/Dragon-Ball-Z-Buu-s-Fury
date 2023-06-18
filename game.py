import pygame

class Game:
    def __init__(self, resolution, caption):
        self.resolution = resolution
        self.caption = caption
        self.set_mode()
        self.set_caption()
        
    def set_mode(self):
        self.screen = pygame.display.set_mode(self.resolution)

    def set_caption(self):
        pygame.display.set_caption(self.caption)
    
    def play_music(self, music, isRunning):
        # Load the sound file
        self.music = music
        pygame.mixer.music.load(self.music)
        # Play the sound
        if(isRunning):
            pygame.mixer.music.play()
        else:
            pygame.mixer.music.stop()
    
    def run(self, isRunning):
        self.isRunning = isRunning
        while self.isRunning:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.isRunning = False

            # Game logic and rendering goes here

            pygame.display.flip()

        pygame.quit()
        
        
