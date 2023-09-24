import pygame
import pytmx
import pyscroll
from saiyan import Saiyan

# Define all constants here
walk_animation_nbr = 4
transform_ssj_nbr = 12

goku_ssj_isTransformed = False
goku_base_json_file = "Config/Goku/Base/goku.json"
goku_ssj_sprite_path = "Graphics/Image_charac/Goku/GokuSS1.png"

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
        
        # Get Goku postion from tmx map
        goku_postion = tmx_data.get_object_by_name("goku")
        
        # Intancite Goku character
        self.character = Saiyan(goku_postion.x , goku_postion.y, goku_ssj_isTransformed, goku_base_json_file)
        
        self.collisions = []
        
        for obj in tmx_data.objects:
            if obj.type == "collision":
                self.collisions.append(pygame.Rect(obj.x, obj.y, obj.width, obj.height))
                # print("{} {} {} {}".format(obj.x, obj.y, obj.width, obj.height))
                # print("\n")

            
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
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Up", walk_animation_nbr)
            else:
                self.character.animate("Walk Up", walk_animation_nbr)
        elif isPressed[pygame.K_DOWN]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Down", walk_animation_nbr)
            else:
                self.character.animate("Walk Down", walk_animation_nbr)
        elif isPressed[pygame.K_RIGHT]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Right", walk_animation_nbr)
            else:
                self.character.animate("Walk Right", walk_animation_nbr)
        elif isPressed[pygame.K_LEFT]:
            if isPressed[pygame.K_SPACE]:
                self.character.animate("Run Left", walk_animation_nbr)
            else:
                self.character.animate("Walk Left", walk_animation_nbr)
        elif isPressed[pygame.K_s]:
            self.character.sprit_sheet = pygame.image.load(goku_ssj_sprite_path)
            self.character.animate("Transform SSJ Down", transform_ssj_nbr)
            self.character.isTransofrmed = True
        else:
            self.character.images = []  # Reset the animation frames
            self.character.current_animation_index = 0
            self.character.sprit_sheet = pygame.image.load("Graphics/Image_charac/Goku/goku.png")


            if self.character.isTransofrmed == False:
                self.character.image = self.character.get_image_by_animation_name("IDLE Down") 
            else:
                self.character.image = self.character.get_image_by_animation_name("IDLE SSJ Down")                 
    
    def update(self):
        self.group.update()       
        for sprite in self.group.sprites():
            if sprite.feet.collidelist(self.collisions) > 1:
                sprite.move_back()
        print("Current postion : {}".format(self.character.position))
        print("Old postion : {}".format(self.character.old_position))
                
    def run(self, isRunning):

        self.isRunning = isRunning
        while self.isRunning:
            self.character.save_location()
            self.keyBoard_input()
            self.update()
            self.group.center(self.character.rect.center)
            self.group.draw(self.screen)
            pygame.display.flip()
            clock = pygame.time.Clock()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.isRunning = False
            clock.tick(60)
        pygame.quit()
        
        
