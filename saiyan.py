from character import Character
import pygame


class Saiyan(Character):
    
    def __init__(self, pos_x, pos_y, isTransformed, json_file):
        super().__init__(pos_x, pos_y, json_file)
        
        self.isTransofrmed = isTransformed
        self.imageTransformIdx = 0
    
    # def animate(self, animation_macro, animation_nbr):
    #     self.images = []
    #     for i in range(animation_nbr):
    #         self.images.append(self.get_image_by_animation_name(animation_macro + " " + str(i)))

    #     self.image = self.images[self.current_animation_index]
    #     if "Left" in animation_macro:
    #         self.image = pygame.transform.flip(self.image, True, False)
    #     self.current_animation_index += 1

    #     if(self.current_animation_index == len(self.images)):
    #         self.current_animation_index = 0
    #     pygame.time.delay(100)
        

