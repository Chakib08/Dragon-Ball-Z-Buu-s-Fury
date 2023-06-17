import pygame

print(pygame)

pygame.display.set_mode((400, 400))
pygame.display.set_caption("Dragon Ball Z Buu's Fury")

# Load the sound file
main_theme = "Sounds/DBZ-Buus-Fury-Soundtrack-Theme.wav"
pygame.mixer.music.load(main_theme)

isRunning = True

while isRunning:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            isRunning = False

pygame.quit()