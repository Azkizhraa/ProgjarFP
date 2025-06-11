import pygame
import sys

def start_loading_screen():
    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 50)

    # Load spinner image (must be circular or symmetrical for best results)
    spinner_image = pygame.image.load("C:\Code\PROGJARiz\images-removebg-preview.png").convert_alpha()
    spinner_rect = spinner_image.get_rect(center=(400, 300))

    angle = 0
    loading_time = 0

    while loading_time < 3600:  # rotate for ~3 seconds (60 FPS)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

        screen.fill((30, 30, 30))

        # Rotate spinner
        rotated_spinner = pygame.transform.rotate(spinner_image, angle)
        rotated_rect = rotated_spinner.get_rect(center=spinner_rect.center)
        screen.blit(rotated_spinner, rotated_rect)

        # Loading text
        text = font.render("Waiting For Opponent", True, (255, 255, 255))
        screen.blit(text, (320, 420))

        pygame.display.flip()
        angle -= 5  # Rotate counter-clockwise (adjust speed if needed)
        loading_time += 1
        clock.tick(60)

# Run directly for testing
if __name__ == "__main__":
    start_loading_screen()
