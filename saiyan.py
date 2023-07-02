from character import Character


class Saiyan(Character):
    
    def __init__(self, pos_x, pos_y, isTransformed, json_file):
        super().__init__(pos_x, pos_y, json_file)
        
        self.isTransofrmed = isTransformed
        self.imageTransformIdx = 0

    
    def transform(self, level, transformation_images):
        
        self.level = level
        self.images = transformation_images
        
        
        
        if(self.level == "Super Saiyan"):
            pass
        