from character import Character


################################################
#                                              #
#   THE CLASS SAIYAN IS NOT IMPLEMENTED YET    #
#                                              #
################################################

class Saiyan(Character):
    
    def __init__(self, pos_x, pos_y, isTransformed, json_file):
        super().__init__(pos_x, pos_y, json_file)
        self.isTransofrmed = isTransformed
        self.rect = self.image.get_rect()