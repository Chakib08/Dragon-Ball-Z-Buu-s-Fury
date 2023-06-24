from character import Character


class Saiyan(Character):
    
    def transform(self, level, transformation_images):
        
        self.level = level
        self.images = transformation_images
        
        
        if(self.level == "Super Saiyan"):
            pass
        