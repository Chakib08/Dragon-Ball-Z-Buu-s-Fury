import pygame

# Initialize Pygame
pygame.init()

pygame.display.set_mode((400, 400))
pygame.display.set_caption("Dragon Ball Z Buu's Fury")

# Load the sound file
main_theme = "Sounds/DBZ-Buus-Fury-Soundtrack-Theme.wav"
pygame.mixer.music.load(main_theme)

# Play the sound
pygame.mixer.music.play()

# Main game loop
clock = pygame.time.Clock()

isRunning = True

while isRunning:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            isRunning = False
            
    # Update the display
    pygame.display.update()
    clock.tick(60)

# Quit the game and Pygame
pygame.mixer.music.stop()
pygame.quit()