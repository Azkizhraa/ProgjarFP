import pygame
import socket
import json
import threading
import sys
import time

# --- Network Configuration ---
SERVER_HOST = '127.0.0.1'  # The server's hostname or IP address
SERVER_PORT = 65432        # The port used by the server

# --- Pygame Initialization ---
pygame.init()

# --- Screen Dimensions ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("RPS Game Client") # Updated title

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
DARK_GRAY = (100, 100, 100)
BLUE = (100, 100, 255)
RED = (255, 100, 100)
GREEN = (100, 255, 100)
YELLOW = (255, 255, 150)

# --- Fonts ---
font_large = pygame.font.Font(None, 74)
font_medium = pygame.font.Font(None, 50)
font_small = pygame.font.Font(None, 36)

# --- Game State Variables (Client-side) ---
player_id = None
game_message = "Connecting to server..."
player_scores = {"0": 0, "1": 0} # Using strings for keys to match JSON parsing
round_status = "connecting" # "connecting", "waiting_for_players", "waiting_for_choices", "round_over"
player_choice = None # The choice made by this client
opponent_choice = None # The choice made by the opponent (revealed after round_over)
round_winner = None # ID of the winner of the last round

# --- RPS Choices ---
CHOICES_MAP = { # Updated for Rock-Paper-Scissors
    0: "Rock",
    1: "Paper",
    2: "Scissors"
}
CHOICE_BUTTONS = [ # Updated for Rock-Paper-Scissors
    {"text": "Rock", "value": 0, "rect": None},
    {"text": "Paper", "value": 1, "rect": None},
    {"text": "Scissors", "value": 2, "rect": None},
]

# --- Network Socket ---
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connected_to_server = False

# --- UI Elements ---
ready_button_rect = pygame.Rect(SCREEN_WIDTH // 2 - 100, SCREEN_HEIGHT - 150, 200, 60)
ready_button_text = "Ready"

# --- Functions for Drawing UI ---

def draw_text(text, font, color, x, y, center=True):
    """Draws text on the screen."""
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect()
    if center:
        text_rect.center = (x, y)
    else:
        text_rect.topleft = (x, y)
    screen.blit(text_surface, text_rect)

def draw_button(rect, text, font, color, text_color, hover_color=None):
    """Draws a button with optional hover effect."""
    mouse_pos = pygame.mouse.get_pos()
    current_color = color
    if hover_color and rect.collidepoint(mouse_pos):
        current_color = hover_color
    pygame.draw.rect(screen, current_color, rect, border_radius=10)
    pygame.draw.rect(screen, BLACK, rect, 3, border_radius=10) # Border
    draw_text(text, font, text_color, rect.centerx, rect.centery)
    return rect.collidepoint(mouse_pos)

def draw_game_screen():
    """Draws all elements of the game screen."""
    screen.fill(DARK_GRAY)

    # Title
    draw_text("Rock Paper Scissors", font_large, YELLOW, SCREEN_WIDTH // 2, 50) # Updated title

    # Player ID
    if player_id is not None:
        draw_text(f"You are Player: {player_id}", font_medium, WHITE, SCREEN_WIDTH // 2, 120)

    # Scores
    draw_text(f"Scores: Player 0: {player_scores.get('0', 0)}  |  Player 1: {player_scores.get('1', 0)}",
              font_medium, WHITE, SCREEN_WIDTH // 2, 180)

    # Game Message
    draw_text(game_message, font_small, WHITE, SCREEN_WIDTH // 2, 240)

    # Choice Buttons
    button_width = 120
    button_height = 80
    start_x = (SCREEN_WIDTH - len(CHOICE_BUTTONS) * (button_width + 20)) // 2 + 10 # Centered with spacing
    start_y = SCREEN_HEIGHT // 2 + 50

    for i, button_data in enumerate(CHOICE_BUTTONS):
        x = start_x + i * (button_width + 20)
        y = start_y
        rect = pygame.Rect(x, y, button_width, button_height)
        button_data["rect"] = rect # Store rect for click detection

        is_hovered = draw_button(rect, button_data["text"], font_small, BLUE if player_choice != button_data["value"] else GREEN, WHITE, hover_color=RED)

        # Highlight selected choice
        if player_choice == button_data["value"]:
            pygame.draw.rect(screen, GREEN, rect, 5, border_radius=10) # Thicker border for selected

    # Ready Button (if applicable)
    if round_status == "waiting_for_players":
        draw_button(ready_button_rect, ready_button_text, font_medium, GREEN, WHITE, hover_color=BLUE)

    # Display round results if round is over
    if round_status == "round_over":
        draw_text(f"Your choice: {CHOICES_MAP.get(player_choice, 'N/A')}", font_small, WHITE, SCREEN_WIDTH // 2, start_y - 100)
        draw_text(f"Opponent's choice: {CHOICES_MAP.get(opponent_choice, 'N/A')}", font_small, WHITE, SCREEN_WIDTH // 2, start_y - 60)
        # Add a "Play Again" or "Next Round" button
        draw_button(ready_button_rect, "Next Round", font_medium, YELLOW, BLACK, hover_color=GREEN)


    pygame.display.flip()

# --- Network Communication Thread ---
def receive_messages():
    """Receives messages from the server in a separate thread."""
    global player_id, game_message, player_scores, round_status, player_choice, opponent_choice, round_winner, connected_to_server
    buffer = ""
    while connected_to_server:
        try:
            data = client_socket.recv(4096).decode('utf-8')
            if not data:
                print("Server disconnected.")
                connected_to_server = False
                game_message = "Server disconnected. Please restart the client."
                break

            buffer += data
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip(): # Skip empty lines
                    continue
                try:
                    message = json.loads(line)
                    msg_type = message.get("type")
                    msg_data = message.get("data")

                    if msg_type == "player_id":
                        player_id = msg_data["id"]
                        print(f"Assigned Player ID: {player_id}")
                        game_message = f"Welcome, Player {player_id}. Waiting for another player..."
                        round_status = "waiting_for_players"
                    elif msg_type == "game_state":
                        game_message = msg_data["message"]
                        player_scores = msg_data["scores"]
                        round_status = msg_data["round_status"]
                        if round_status == "waiting_for_choices":
                            player_choice = None # Reset player choice for new round
                            opponent_choice = None
                            round_winner = None
                        print(f"Game State Update: {game_message} (Status: {round_status})")
                    elif msg_type == "round_result":
                        game_message = msg_data["message"]
                        player_scores = msg_data["scores"]
                        round_status = msg_data["round_status"] # Should be "round_over"
                        round_winner = msg_data["winner"]
                        # Determine opponent's choice based on which player we are
                        if player_id == 0:
                            opponent_choice = msg_data["player1_choice"] # Server sends choice string now
                        else:
                            opponent_choice = msg_data["player0_choice"] # Server sends choice string now

                        print(f"Round Result: {game_message}")
                        print(f"Player 0 choice: {msg_data['player0_choice']}, Player 1 choice: {msg_data['player1_choice']}")
                        print(f"Current Scores: {player_scores}")

                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e} - Data: {line}")
                except Exception as e:
                    print(f"Error processing message: {e} - Data: {line}")

        except socket.error as e:
            print(f"Socket error: {e}")
            connected_to_server = False
            game_message = "Connection lost to server."
            break
        except Exception as e:
            print(f"Unexpected error in receive_messages: {e}")
            connected_to_server = False
            break

def send_message(message_type, data):
    """Sends a message to the server."""
    global connected_to_server
    if connected_to_server:
        message = json.dumps({"type": message_type, "data": data}) + "\n"
        try:
            client_socket.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"Failed to send message: {e}")
            connected_to_server = False
            game_message = "Connection lost while sending data."

# --- Main Game Loop ---
def game_loop():
    global connected_to_server, player_choice, round_status, game_message

    try:
        client_socket.connect((SERVER_HOST, SERVER_PORT))
        connected_to_server = True
        print(f"Connected to server at {SERVER_HOST}:{SERVER_PORT}")
        # Start a thread to receive messages from the server
        receive_thread = threading.Thread(target=receive_messages, daemon=True)
        receive_thread.start()
    except socket.error as e:
        game_message = f"Could not connect to server: {e}"
        print(game_message)
        connected_to_server = False

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1: # Left click
                    mouse_x, mouse_y = event.pos

                    if connected_to_server:
                        if round_status == "waiting_for_players":
                            if ready_button_rect.collidepoint(mouse_x, mouse_y):
                                send_message("ready", {})
                                game_message = "Waiting for opponent to be ready..."
                                round_status = "waiting_for_opponent_ready" # Custom client-side status
                        elif round_status == "waiting_for_choices":
                            for button_data in CHOICE_BUTTONS:
                                if button_data["rect"] and button_data["rect"].collidepoint(mouse_x, mouse_y):
                                    player_choice = button_data["value"]
                                    send_message("choice", {"choice": player_choice})
                                    game_message = f"You chose {CHOICES_MAP[player_choice]}. Waiting for opponent..."
                                    round_status = "choice_made" # Custom client-side status
                                    break
                        elif round_status == "round_over":
                            if ready_button_rect.collidepoint(mouse_x, mouse_y):
                                # Signal server for next round (though server auto-resets)
                                # This button primarily resets client UI for next round
                                round_status = "waiting_for_choices"
                                player_choice = None
                                opponent_choice = None
                                round_winner = None
                                game_message = "New round! Make your choice."
                                # No explicit message to server needed here as server is always ready for choices
                                # send_message("next_round", {}) # Could be used if server needed explicit ready for next round

        draw_game_screen()

        if not connected_to_server and running:
            # If disconnected, allow user to quit or try reconnecting (not implemented yet)
            # For now, just keep displaying the message and wait for quit.
            pass

        pygame.time.Clock().tick(60) # Limit frame rate to 60 FPS

    # --- Cleanup ---
    if connected_to_server:
        client_socket.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    game_loop()
