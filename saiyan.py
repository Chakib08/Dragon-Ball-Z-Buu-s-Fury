from character import Character
import pygame


class Saiyan(Character):
    
    def __init__(self, pos_x, pos_y, isTransformed, json_file):
        super().__init__(pos_x, pos_y, json_file)
        
        self.isTransofrmed = isTransformed
        self.rect = self.image.get_rect()
        self.side = "Right"

    def move(self, side, speed):
        super().move(side, speed)
    
    
    def animate(self, animation_macro, animation_nbr):
        super().animate(animation_macro, animation_nbr)
        

        # Check if the Transofrm string is in the animation macro retreived from the json file
        if "Transform" in animation_macro:
            macro, level, side = animation_macro.split()
        else:
            macro, side = animation_macro.split()
                
        if macro == "Walk":
            self.speed = 4
            self.move(side, self.speed)
        elif macro == "Run":
            self.speed = 8
            self.move(side, self.speed)
        # TODO: Implement Attack
        

