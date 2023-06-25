import pygame
import pytmx
import pyscroll
from character import Character
from saiyan import Saiyan


# Define the character size by the image resolution 32x32
character_size = [24,31]

# Define image character
goku_img = "Graphics/Image_charac/Goku/goku.png"
goku_posX = 120
goku_posY = 30
goku_imgX = 1
goku_imgY = 2
goku_background = (0, 64, 64)


# Define goku super saiyan transformation images
goku_ssj1 = "Graphics/Image_charac/Goku/GokuSS1.png"
goku_ssj1_bg = (0, 128, 0)
goku_ssj_animations = [
[6, 377, 32, 33, [32, 33]],
[44, 377, 32, 33, [32, 33]],
[80, 376, 32, 33, [32, 33]],
[155, 377, 32, 34, [32, 34]],
[193, 377, 32, 34, [32, 34]],
[234, 377, 32, 34, [32, 34]],
[274, 377, 32, 34, [32, 34]],
[312, 377, 32, 34, [32, 34]],
[349, 377, 32, 33, [32, 33]],
[349, 377, 32, 33, [32, 33]],
[386, 377, 32, 33, [32, 33]],
[424, 377, 32, 33, [32, 33]]]

goku_ssj_isTransformed = False

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
        self.speed = 4
        
        # Get Goku postion from tmx map
        goku_postion = tmx_data.get_object_by_name("goku")
        
        # Intancite Goku character
        self.character = Saiyan(goku_postion.x , goku_postion.y, goku_imgX, goku_imgY, 32, 32, goku_img, character_size, goku_background, goku_ssj_isTransformed)

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
        
        if isPressed[pygame.K_UP]:
            self.character.sprit_sheet = pygame.image.load(goku_img)

            # Set image where the sprite walks up
            self.character.images = [
                self.character.get_img(28, 67, 32, 32, [24, 32]),
                self.character.get_img(53, 68, 32, 32, [25, 31]),
                self.character.get_img(79, 68, 32, 32, [24, 31]),
                self.character.get_img(104, 68, 32, 32, [25, 31]),
                # Add more images for the walking animation
            ]
            self.character.image = self.character.images[self.character.imageIdx]
            self.character.imageIdx += 1
            if(self.character.imageIdx == len(self.character.images)):
                self.character.imageIdx = 0
            
            self.character.image.set_colorkey(goku_background)
            pygame.time.delay(100)
            self.character.move("up", self.speed)
        
        elif isPressed[pygame.K_DOWN]:
            self.character.sprit_sheet = pygame.image.load(goku_img)
            # Set image where the sprite walks down
            self.character.images = [
                self.character.get_img(54, 3, 32, 32, [25, 30]),
                self.character.get_img(80, 3, 32, 32, [25, 30]),
                self.character.get_img(106, 2, 32, 32, [25, 31]),
                self.character.get_img(132, 3, 32, 32, [25, 30]),
                # Add more images for the walking animation
            ]
            self.character.image = self.character.images[self.character.imageIdx]
            self.character.imageIdx += 1
            if(self.character.imageIdx == len(self.character.images)):
                self.character.imageIdx = 0
            
            self.character.image.set_colorkey(goku_background)
            pygame.time.delay(100)
            self.character.move("down", self.speed)

        elif isPressed[pygame.K_RIGHT]:
            self.character.sprit_sheet = pygame.image.load(goku_img)
            # Set image where the sprite walks right
            self.character.images = [
                self.character.get_img(50, 35, 32, 32, [22, 31]),
                self.character.get_img(73, 35, 32, 32, [23, 31]),
                self.character.get_img(97, 36, 32, 32, [24, 30]),
                self.character.get_img(122, 35, 32, 32, [23, 31]),
            ]
            self.character.image = self.character.images[self.character.imageIdx]
            self.character.imageIdx += 1
            if(self.character.imageIdx == len(self.character.images)):
                self.character.imageIdx = 0
            
            self.character.image.set_colorkey(goku_background)
            pygame.time.delay(100)
            self.character.move("right", self.speed)

        elif isPressed[pygame.K_LEFT]:
            self.character.sprit_sheet = pygame.image.load(goku_img)
            # Set image where the sprite walks left
            self.character.images = [
                self.character.get_img(50, 35, 32, 32, [22, 31]),
                self.character.get_img(73, 35, 32, 32, [23, 31]),
                self.character.get_img(97, 36, 32, 32, [24, 30]),
                self.character.get_img(122, 35, 32, 32, [23, 31]),
            ]
            
            self.character.image = self.character.images[self.character.imageIdx]
            self.character.image = pygame.transform.flip(self.character.image, True, False)
            self.character.imageIdx += 1
            if(self.character.imageIdx == len(self.character.images)):
                self.character.imageIdx = 0
            self.character.image.set_colorkey(goku_background)
            pygame.time.delay(100)
            self.character.move("left", self.speed)
        
        elif isPressed[pygame.K_SPACE] and self.character.isTransofrmed == False:
                self.character.sprit_sheet = pygame.image.load(goku_ssj1)
                self.character.images = []  # Reset the animation frames
                for animation in range(len(goku_ssj_animations)):
                    self.character.images.append(self.character.get_img(goku_ssj_animations[animation][0], goku_ssj_animations[animation][1], goku_ssj_animations[animation][2], goku_ssj_animations[animation][3], goku_ssj_animations[animation][4]))
                
                self.character.image = self.character.images[self.character.imageTransformIdx]
                self.character.imageTransformIdx += 1

                self.character.image.set_colorkey(goku_ssj1_bg)
                pygame.time.delay(100)
                if(self.character.imageTransformIdx== len(self.character.images)):
                    self.character.isTransofrmed = True
                print(self.character.isTransofrmed)
                     
        
        else:
            self.character.images = []  # Reset the animation frames
            
            if self.character.isTransofrmed == False:
                self.character.sprit_sheet = pygame.image.load(goku_img)
                self.character.image = self.character.get_img(1, 2, 32, 32, [24, 31])
                self.character.image.set_colorkey(goku_background)
            else:
                self.character.sprit_sheet = pygame.image.load(goku_ssj1)
                self.character.image = self.character.get_img(29, 452, 32, 32, [16, 31])
                self.character.image.set_colorkey(goku_ssj1_bg)
                     
            
    
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
        
        
