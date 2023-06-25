from character import Character


class Saiyan(Character):
    
    def __init__(self, pos_x, pos_y, img_x, img_y, area_width, area_height, charac_img, size, background, isTransformed):
        super().__init__(pos_x, pos_y, img_x, img_y, area_width, area_height, charac_img, size, background)
        
        self.isTransofrmed = isTransformed
    
    def transform(self, level, transformation_images):
        
        self.level = level
        self.images = transformation_images
        
        
        
        if(self.level == "Super Saiyan"):
            pass
        