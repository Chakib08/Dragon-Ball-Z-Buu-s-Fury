import pygame

####################################################
#                                                  #
#   THE CLASS PYGAMEHELPER IS NOT YET IMPLEMENTED  #
#                                                  #
####################################################

class PygameHelper:
    
    @classmethod
    def play_music(self, music):
        # Load the sound file
        pygame.mixer.music.stop()
        pygame.mixer.music.load(music)
        # Play the sound
        pygame.mixer.music.play(-1)  # Play music indefinitely