import pygame
import pytmx
import pyscroll
from character import Character


# Define the character size by the image resolution 32x32
character_size = [24,31]

# Define image character
goku_img = "Graphics/Image_charac/Goku/goku.png"
goku_posX = 120
goku_posY = 30
goku_background = [0, 64, 64]

class Game:
    def __init__(self, resolution, caption, tmx_map):
        # Initialize game window
        self.resolution = resolution
        self.caption = caption
        self.tmx_map = tmx_map
        self.screen = self.set_mode()
        self.set_caption()
        
        # Load tmx utils to handle the game's map
        tmx_data = pytmx.load_pygame(self.tmx_map)
        map_data = pyscroll.data.TiledMapData(tmx_data)
        map_layer = pyscroll.orthographic.BufferedRenderer(map_data, self.resolution)
        map_layer.zoom = 1
        
        # Character param
        self.speed = 2
        
        # Get Goku postion from tmx map
        goku_postion = tmx_data.get_object_by_name("goku")
        
        # Intancite Goku character
        self.character = Character(goku_postion.x , goku_postion.y, goku_img, character_size, goku_background)

        # Draw layers groups
        self.group = pyscroll.PyscrollGroup(map_layer=map_layer, default_layer=1)
        
        # Add your layers here (like characters etc.)
        self.group.add(self.character)
        
    def set_mode(self):
        return pygame.display.set_mode(self.resolution)

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
            
    def keyBoard_input(self):
        isPressed = pygame.key.get_pressed()
        
        if(isPressed[pygame.K_UP]):
            self.character.move("up", self.speed)
        
        elif(isPressed[pygame.K_DOWN]):
            self.character.move("down", self.speed)

        elif(isPressed[pygame.K_RIGHT]):
            self.character.move("right", self.speed)

        elif(isPressed[pygame.K_LEFT]):
            self.character.move("left", self.speed)
        
        else:
            pass

       
    
    def run(self, isRunning):
        clock = pygame.time.Clock()
        self.isRunning = isRunning
        while self.isRunning:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.isRunning = False
            clock.tick(60)
            # Game logic and rendering goes here
            self.keyBoard_input()
            self.group.update()
            self.group.draw(self.screen)
            pygame.display.flip()
            

        pygame.quit()
        
        
