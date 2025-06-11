import pygame
import sys

import pygame.image

pygame.init()
screen = pygame.display.set_mode((800, 600))
font1 = pygame.font.Font(None, 60)
font2 = pygame.font.Font(None, 50)
font_input = pygame.font.Font(None, 40)
clock = pygame.time.Clock()

icon_1 = pygame.image.load("C:\Code\PROGJARiz\Group.png")
icon_2 = pygame.image.load("C:\Code\PROGJARiz\Group1.png")
icon_3 = pygame.image.load("C:\Code\PROGJARiz\Group2.png")

icon_1 = pygame.transform.scale(icon_1, (80, 100))
icon_2 = pygame.transform.scale(icon_2, (100, 100))
icon_3 = pygame.transform.scale(icon_3, (120, 100))



# State for input box
user_text = ""
input_active = False  # True when the text box is selected

def home_screen(user_text, input_active):
    screen.fill((220, 153, 64))
    title = font1.render("Rock Paper Scissors But Better", True, (255, 255, 255))
    ready_text = font2.render("Ready", True, (255, 255, 255))
    exit_text = font2.render("Exit", True, (255, 255, 255))

    cor_x, cor_y = pygame.mouse.get_pos()

    if 310 <= cor_x <= 560 and 340 <= cor_y <= 420:
        button_color1 = (86, 87, 85)
    else:
        button_color1 = (111, 111, 110)

    if 310 <= cor_x <= 560 and 450 <= cor_y <= 530:
        button_color2 = (86, 87, 85)
    else:
        button_color2 = (111, 111, 110)

    pygame.draw.rect(screen, button_color1, (310, 340, 250, 80))  # Ready
    pygame.draw.rect(screen, button_color2, (310, 450, 250, 80))  # Exit
    pygame.draw.rect(screen, (255, 255, 255), (310, 260, 250, 60))  # Input box border

    # Highlight input box if active
    input_box_color = (255, 255, 255) if input_active else (200, 200, 200)
    pygame.draw.rect(screen, input_box_color, (315, 265, 240, 50))  # Input box inner

    screen.blit(title, (100, 200))
    screen.blit(ready_text, (380, 360))
    screen.blit(exit_text, (400, 470))

    screen.blit(icon_1, ( 100, 80))
    screen.blit(icon_2, ( 350, 80))
    screen.blit(icon_3, ( 600, 80))

    # Render input text
    input_surface = font_input.render(user_text, True, (0, 0, 0))
    screen.blit(input_surface, (325, 275))

    pygame.display.flip()

def main_screen():
    global user_text, input_active
    user_text = ""
    input_active = False

    while True:
        home_screen(user_text, input_active)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                x, y = event.pos
                # Activate input box
                if 310 <= x <= 560 and 260 <= y <= 320:
                    input_active = True
                else:
                    input_active = False

                # Check if Ready button clicked
                if 310 <= x <= 560 and 340 <= y <= 420:
                    print("Name entered:", user_text)
                    return

                # Exit button
                if 310 <= x <= 560 and 450 <= y <= 530:
                    pygame.quit()
                    sys.exit()

            elif event.type == pygame.KEYDOWN and input_active:
                if event.key == pygame.K_BACKSPACE:
                    user_text = user_text[:-1]
                elif event.key == pygame.K_RETURN:
                    input_active = False
                else:
                    if len(user_text) < 20:
                        user_text += event.unicode

        clock.tick(60)

if __name__ == "__main__":
    main_screen()
