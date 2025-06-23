import pygame
import socket
import pickle
import threading
import sys
import time
import os
import random

# --- Network Configuration ---
SERVER_HOST = '127.0.0.1' 
SERVER_PORT = 65432
HEADER_LENGTH = 10 

# --- Pygame Initialization ---
pygame.init()

# --- Screen Dimensions ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.RESIZABLE)
pygame.display.set_caption("RPS Game Client")
fullscreen = False

# --- Colors ---
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)
DARK_GRAY = (100, 100, 100)
BLUE = (100, 100, 255)
RED = (255, 100, 100)
GREEN = (100, 255, 100)
YELLOW = (255, 255, 150)
HP_RED = (200, 0, 0)
HP_YELLOW = (255, 220, 0)
HP_GREEN = (0, 200, 0)
SHADOW_COLOR = (50, 50, 50)
GAME_OVER_RED = (249, 4, 4)

# --- Fonts ---
try:
    font_name = 'BADABB__.TTF'
    font_large = pygame.font.Font(font_name, 74)
    font_medium = pygame.font.Font(font_name, 50)
    font_small = pygame.font.Font(font_name, 36)
    font_hp = pygame.font.Font(font_name, 28)
    font_card_name = pygame.font.Font(font_name, 28) 
    font_card_effect = pygame.font.Font(font_name, 22)
    font_round_result = pygame.font.Font(font_name, 48)
    font_section_title = pygame.font.Font(font_name, 40)
    font_end_screen = pygame.font.Font(font_name, 150)
except FileNotFoundError:
    print("Warning: Font 'BADABB__.TTF' not found. Falling back to default font.")
    font_name = None
    font_large = pygame.font.Font(None, 74); font_medium = pygame.font.Font(None, 50); font_small = pygame.font.Font(None, 36); font_hp = pygame.font.Font(None, 28); font_card_name = pygame.font.Font(None, 28); font_card_effect = pygame.font.Font(None, 22); font_round_result = pygame.font.Font(None, 48); font_section_title = pygame.font.Font(None, 40); font_end_screen = pygame.font.Font(None, 150)


# --- Game State Variables (Client-side) ---
player_id = None
game_message = "Connecting to server..."
player_hps = {0: 100, 1: 100}
player_names = {0: "Player 0", 1: "Player 1"}
round_status = "entering_username" 
player_choice = None
game_over = False
local_player_won = False
player_hand = []
revealed_player_card_data = None
revealed_opponent_card_data = None

# --- Username Input State ---
username = ""
input_box_active = False

# --- Animation State ---
end_screen_text_scale = 0.0
end_screen_animation_active = False
end_screen_text_velocity = 0.0
spring = 0.04
damping = 0.75
last_known_hps = {0: 100, 1: 100}
hp_shake_info = {
    0: {"is_shaking": False, "duration": 0, "intensity": 4},
    1: {"is_shaking": False, "duration": 0, "intensity": 4}
}

# --- UI and Game Constants ---
INITIAL_HP = 100
CHOICES_MAP = {0: "Rock", 1: "Paper", 2: "Scissors"}
CARD_EFFECTS_DISPLAY = { "none": "No Effect", "power_attack": "Power Attack (20 Dmg)", "counter_damage_5": "Counter (5 Dmg if Lose)"}
NORMAL_SCALE, HOVER_SCALE, SCALE_SPEED = 1.0, 1.1, 0.08
TILT_ANGLE = 10 
TILT_SPEED = 0.1 

# --- Asset Loading ---
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'assets')
MAX_CARD_IMAGE_HEIGHT = 120
card_images = { 0: {0: None, 1: None, 2: None}, 1: {0: None, 1: None, 2: None}, 'default': {0: None, 1: None, 2: None}}
player_0_background, player_1_background = None, None
win_screen_img, lose_screen_img = None, None
hp_bar_bg_img, heart_icon_img = None, None
ready_bg_img, avatar0_img, avatar1_img = None, None, None
join_bg0_img, join_bg1_img = None, None

def load_and_scale_image(file_name, max_height):
    path = os.path.join(ASSETS_DIR, file_name)
    try:
        original_image = pygame.image.load(path).convert_alpha()
        padding = 5 
        padded_size = (original_image.get_width() + 2 * padding, original_image.get_height() + 2 * padding)
        padded_surface = pygame.Surface(padded_size, pygame.SRCALPHA)
        padded_surface.blit(original_image, (padding, padding))
        image_to_scale = padded_surface
        if max_height > 0:
            w, h = image_to_scale.get_size()
            scale = max_height / h
            return pygame.transform.smoothscale(image_to_scale, (int(w * scale), max_height))
        return image_to_scale
    except (pygame.error, FileNotFoundError) as e:
        print(f"Warning: Could not load {file_name}. {e}")
        return None

player_0_background = load_and_scale_image('player2screen_bg.png', 0)
player_1_background = load_and_scale_image('player1screen_bg.png', 0)
win_screen_img = load_and_scale_image('win_screen.png', 0)
lose_screen_img = load_and_scale_image('lose_screen.png', 0)
hp_bar_bg_img = load_and_scale_image('hp_bar_bg.png', 0)
heart_icon_img = load_and_scale_image('heart_icon.png', 0)
ready_bg_img = load_and_scale_image('ready_bg.png', 0)
avatar0_img = load_and_scale_image('avatar0.png', 0)
avatar1_img = load_and_scale_image('avatar1.png', 0)
join_bg0_img = load_and_scale_image('join_bg0.png', 0)
join_bg1_img = load_and_scale_image('join_bg1.png', 0) 


for p_id in [0, 1, 'default']:
    for rps_val in [0, 1, 2]:
        suffix = str(p_id) if p_id != 'default' else ''
        filename = f"{CHOICES_MAP[rps_val].lower()}{suffix}.png"
        card_images[p_id][rps_val] = load_and_scale_image(filename, MAX_CARD_IMAGE_HEIGHT)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
connected_to_server = False

# --- Drawing Functions ---
def draw_text_with_shadow(text, font, color, x, y, center=True, stroke=True):
    text_surface = font.render(text, True, color)
    shadow_surface = font.render(text, True, SHADOW_COLOR)
    shadow_rect = shadow_surface.get_rect(center=(x + 3, y + 3) if center else (x + 3, y + 3))
    screen.blit(shadow_surface, shadow_rect)
    if stroke:
        stroke_surface = font.render(text, True, BLACK)
        stroke_offsets = [(-1, -1), (1, -1), (-1, 1), (1, 1), (-1, 0), (1, 0), (0, -1), (0, 1)]
        for dx, dy in stroke_offsets:
            stroke_rect = stroke_surface.get_rect(center=(x + dx, y + dy) if center else (x + dx, y + dy))
            screen.blit(stroke_surface, stroke_rect)
    text_rect = text_surface.get_rect(center=(x, y) if center else (x,y))
    screen.blit(text_surface, text_rect)

def draw_wrapped_text_with_shadow(text, font, color, rect):
    def get_lines(txt, f, max_width):
        words = txt.split(' ')
        lines = []
        current_line = ""
        for word in words:
            if f.size(current_line + word)[0] < max_width:
                current_line += word + " "
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)
        return lines
    lines = get_lines(text, font, rect.width)
    y_start = rect.top
    last_line_y = y_start
    for i, line in enumerate(lines):
        line_y_pos = y_start + i * font.get_linesize()
        draw_text_with_shadow(line.strip(), font, color, rect.centerx, line_y_pos)
        last_line_y = line_y_pos
    return last_line_y + font.get_linesize()

def draw_hp_bar(current_hp, max_hp, x, y, width, height, player_label, shake_offset=(0, 0)):
    x += shake_offset[0]
    y += shake_offset[1]
    if not hp_bar_bg_img or not heart_icon_img: return
    if current_hp < 0: current_hp = 0
    hp_ratio = current_hp / max_hp
    scaled_bg = pygame.transform.smoothscale(hp_bar_bg_img, (width, height))
    bg_rect = scaled_bg.get_rect(topleft=(x, y))
    screen.blit(scaled_bg, bg_rect)
    if hp_ratio > 0.6: hp_color = HP_GREEN
    elif hp_ratio > 0.3: hp_color = HP_YELLOW
    else: hp_color = HP_RED
    padding = height * 0.18
    fill_width = (width - 2 * padding) * hp_ratio
    fill_height = height - 2 * padding
    fill_rect = pygame.Rect(x + padding, y + padding, fill_width, fill_height)
    pygame.draw.rect(screen, hp_color, fill_rect, border_radius=int(fill_height / 2))
    icon_size = int(height * 1.5)
    scaled_icon = pygame.transform.smoothscale(heart_icon_img, (icon_size, icon_size))
    icon_rect = scaled_icon.get_rect(center=(x + padding, bg_rect.centery))
    screen.blit(scaled_icon, icon_rect)
    hp_text = str(int(current_hp))
    draw_text_with_shadow(hp_text, font_hp, WHITE, bg_rect.centerx + (icon_size / 4), bg_rect.centery)
    draw_text_with_shadow(player_label, font_small, WHITE, bg_rect.centerx, bg_rect.top - 20)

def draw_button(rect, text, font, color, text_color, hover_color=None):
    mouse_pos = pygame.mouse.get_pos()
    is_hovered = rect.collidepoint(mouse_pos)
    current_color = hover_color if is_hovered and hover_color else color
    
    shadow_rect = rect.move(5, 5)
    pygame.draw.rect(screen, (0,0,0,100), shadow_rect, border_radius=12)

    pygame.draw.rect(screen, current_color, rect, border_radius=10)
    pygame.draw.rect(screen, BLACK, rect, 3, border_radius=10)
    draw_text_with_shadow(text, font, text_color, rect.centerx, rect.centery)
    return is_hovered

def draw_card_as_image_button(x, y, card_data, is_selected, is_clickable=True, extra_scale=1.0):
    rps_value = card_data["rps_value"]
    effect_text = CARD_EFFECTS_DISPLAY.get(card_data["effect"], "Unknown")
    card_name = CHOICES_MAP.get(rps_value, "???")
    owner_id = card_data.get("owner", player_id) 
    image_set = card_images.get(owner_id, card_images['default'])
    base_image = image_set.get(rps_value, card_images['default'].get(rps_value))
    if not base_image: return pygame.Rect(x, y, 0, 0)
    
    current_scale = card_data.get("current_scale", NORMAL_SCALE) * extra_scale
    current_tilt = card_data.get("current_tilt", 0)
    scaled_w = int(base_image.get_width() * current_scale)
    scaled_h = int(base_image.get_height() * current_scale)
    if scaled_w <= 0 or scaled_h <= 0: return pygame.Rect(x,y,0,0)

    scaled_image = pygame.transform.smoothscale(base_image, (scaled_w, scaled_h))
    display_image = scaled_image
    
    if is_selected:
        border_padding = 20 * extra_scale 
        bordered_surface_size = (scaled_w + border_padding, scaled_h + border_padding)
        bordered_surface = pygame.Surface(bordered_surface_size, pygame.SRCALPHA)
        pygame.draw.rect(bordered_surface, GREEN, bordered_surface.get_rect(), int(4 * extra_scale), border_radius=int(12 * extra_scale))
        card_pos_in_surface = (border_padding / 2, border_padding / 2)
        bordered_surface.blit(scaled_image, card_pos_in_surface)
        display_image = pygame.transform.rotozoom(bordered_surface, current_tilt, 1)

    image_rect = display_image.get_rect(centerx=x, top=y)
    screen.blit(display_image, image_rect)

    scaled_name_size = max(1, int(24 * extra_scale))
    scaled_effect_size = max(1, int(18 * extra_scale))
    scaled_name_font = pygame.font.Font(font_name, scaled_name_size)
    scaled_effect_font = pygame.font.Font(font_name, scaled_effect_size)

    text_y_anchor = image_rect.bottom + (15 * extra_scale)
    draw_text_with_shadow(card_name, scaled_name_font, WHITE, x, text_y_anchor)
    draw_text_with_shadow(effect_text, scaled_effect_font, WHITE, x, text_y_anchor + (30 * extra_scale))
    
    name_rect = scaled_name_font.render(card_name, True, WHITE).get_rect(centerx=x, top=text_y_anchor)
    effect_rect = scaled_effect_font.render(effect_text, True, WHITE).get_rect(centerx=x, top=name_rect.bottom)
    interaction_rect = image_rect.unionall([name_rect, effect_rect])
    return interaction_rect

def draw_game_screen(sw, sh, shake_offsets):
    if round_status == "entering_username":
        bg_img = join_bg1_img if player_id == 1 and join_bg1_img else join_bg0_img
        avatar_img = avatar1_img if player_id == 1 and avatar1_img else avatar0_img

        if bg_img:
            screen.blit(pygame.transform.smoothscale(bg_img, (sw, sh)), (0, 0))
        else:
            screen.fill((27, 133, 93))
        
        if avatar_img:
            avatar_size = int(sw * 0.18)
            scaled_avatar = pygame.transform.smoothscale(avatar_img, (avatar_size, avatar_size))
            avatar_rect = scaled_avatar.get_rect(center=(sw * 0.72, sh * 0.45))
            screen.blit(scaled_avatar, avatar_rect)
        
        input_pos_x = sw * 0.4
        input_pos_y = sh * 0.45
        
        if not username and not input_box_active:
            draw_text_with_shadow("INSERT NAME", font_large, WHITE, input_pos_x, input_pos_y)
        else:
            display_text = username
            if input_box_active and time.time() % 1 > 0.5:
                display_text += '_'
            draw_text_with_shadow(display_text, font_large, WHITE, input_pos_x, input_pos_y)
            
        join_button_rect = pygame.Rect(sw / 2 - 125, sh * 0.8, 250, 70)
        join_button_color = (253, 192, 47) 
        join_button_hover_color = (255, 210, 80)
        draw_button(join_button_rect, "JOIN", font_medium, join_button_color, WHITE, hover_color=join_button_hover_color)

        return

    if round_status == "waiting_for_players":
        if ready_bg_img:
            screen.blit(pygame.transform.smoothscale(ready_bg_img, (sw, sh)), (0, 0))
        else:
            screen.fill(DARK_GRAY)
        
        draw_text_with_shadow("ROCK PAPER SCISSORS", font_large, YELLOW, sw / 2, sh * 0.1)

        p1_name = player_names.get(1, "Player 1")
        avatar_size_1 = int(sw * 0.12)
        avatar_x_1, avatar_y_1 = sw * 0.22, sh * 0.60
        
        if avatar1_img:
            scaled_avatar_1 = pygame.transform.smoothscale(avatar1_img, (avatar_size_1, avatar_size_1))
            avatar_pos_1 = (avatar_x_1 - avatar_size_1 / 2, avatar_y_1 - avatar_size_1 / 2)
            screen.blit(scaled_avatar_1, avatar_pos_1)
            if player_id == 1:
                draw_text_with_shadow("(YOU)", font_small, WHITE, avatar_x_1, avatar_pos_1[1] - 30)
        
        text_y_1 = avatar_y_1 + avatar_size_1 * 0.85 
        if p1_name != "Player 1":
            draw_text_with_shadow(f"{p1_name.upper()} HAS JOINED", font_small, WHITE, avatar_x_1, text_y_1)
        else:
            draw_text_with_shadow("WAITING...", font_small, GRAY, avatar_x_1, text_y_1)
            
        p0_name = player_names.get(0, "Player 0")
        avatar_size_0 = int(sw * 0.12)
        avatar_x_0, avatar_y_0 = sw * 0.75, sh * 0.35

        if avatar0_img:
            scaled_avatar_0 = pygame.transform.smoothscale(avatar0_img, (avatar_size_0, avatar_size_0))
            avatar_pos_0 = (avatar_x_0 - avatar_size_0 / 2, avatar_y_0 - avatar_size_0 / 2)
            screen.blit(scaled_avatar_0, avatar_pos_0)
            if player_id == 0:
                draw_text_with_shadow("(YOU)", font_small, WHITE, avatar_x_0, avatar_pos_0[1] - 30)

        text_y_0 = avatar_y_0 + avatar_size_0 * 0.85
        if p0_name != "Player 0":
            draw_text_with_shadow(f"{p0_name.upper()} HAS JOINED", font_small, WHITE, avatar_x_0, text_y_0)
        else:
            draw_text_with_shadow("WAITING...", font_small, GRAY, avatar_x_0, text_y_0)
        
        return

    bg = player_1_background if player_id == 1 else player_0_background
    if bg: screen.blit(pygame.transform.scale(bg, (sw, sh)), (0, 0))
    else: screen.fill(DARK_GRAY)

    # --- MODIFICATION ---
    # The game_over screen is now the final screen before the server resets the state.
    # No button is needed here anymore.
    if game_over:
        end_bg = win_screen_img if local_player_won else lose_screen_img
        if end_bg: screen.blit(pygame.transform.scale(end_bg, (sw, sh)), (0, 0))
        else: screen.fill(DARK_GRAY)
        
        end_text_str = "YOU WIN!" if local_player_won else "GAME OVER!"
        end_text_color = WHITE if local_player_won else GAME_OVER_RED
        text_surface = font_end_screen.render(end_text_str, True, end_text_color)
        scaled_width = int(text_surface.get_width() * end_screen_text_scale)
        scaled_height = int(text_surface.get_height() * end_screen_text_scale)
        if scaled_width > 0 and scaled_height > 0:
            scaled_text = pygame.transform.smoothscale(text_surface, (scaled_width, scaled_height))
            text_rect = scaled_text.get_rect(center=(sw / 2, sh / 2))
            draw_text_with_shadow(end_text_str, pygame.font.Font(font_name, scaled_height), end_text_color, text_rect.centerx, text_rect.centery)
        return

    is_large_screen = sw > 950 or sh > 650

    if is_large_screen:
        title_y, player_info_y, hp_bar_y, hp_bar_width, hp_bar_height = sh * 0.08, sh * 0.18, sh * 0.26, 300, 50
    else:
        title_y, player_info_y, hp_bar_y, hp_bar_width, hp_bar_height = 50, 120, 180, 240, 40

    if player_id is not None and not game_over:
        insta_win_rect = pygame.Rect(sw - 160, 10, 150, 40)
        draw_button(insta_win_rect, "Insta-Win", font_small, RED, WHITE, hover_color=BLUE)

    draw_text_with_shadow("Rock Paper Scissors", font_large, YELLOW, sw / 2, title_y)
    if player_id is not None:
        your_name = player_names.get(player_id, "")
        draw_text_with_shadow(f"YOU ARE: {your_name.upper()}", font_medium, WHITE, sw / 2, player_info_y)
    
    draw_hp_bar(player_hps.get(1, 0), INITIAL_HP, sw / 2 - hp_bar_width - 20, hp_bar_y, hp_bar_width, hp_bar_height, player_names.get(1, "Player 1"), shake_offsets[1])
    draw_hp_bar(player_hps.get(0, 0), INITIAL_HP, sw / 2 + 20, hp_bar_y, hp_bar_width, hp_bar_height, player_names.get(0, "Player 0"), shake_offsets[0])
    
    content_start_y = hp_bar_y + hp_bar_height + (35 * (sh/SCREEN_HEIGHT))
    
    if round_status == "round_over":
        summary_rect = pygame.Rect(50, content_start_y, sw - 100, sh * 0.3)
        message_bottom_y = draw_wrapped_text_with_shadow(game_message, font_small, YELLOW, summary_rect)
        revealed_y_pos = message_bottom_y + 20 
        card_scale = 1.0
        
        draw_text_with_shadow(f"{player_names.get(1, 'Player 1')}'s Card", font_small, WHITE, sw/4, revealed_y_pos)
        draw_text_with_shadow(f"{player_names.get(0, 'Player 0')}'s Card", font_small, WHITE, sw * 3/4, revealed_y_pos)
        
        p0_card = revealed_player_card_data if player_id == 0 else revealed_opponent_card_data
        p1_card = revealed_opponent_card_data if player_id == 0 else revealed_player_card_data

        if p0_card and p1_card:
            p0_card["owner"] = 0; p1_card["owner"] = 1
            draw_card_as_image_button(sw/4, revealed_y_pos + 25, p1_card, False, is_clickable=False, extra_scale=card_scale)
            draw_card_as_image_button(sw * 3/4, revealed_y_pos + 25, p0_card, False, is_clickable=False, extra_scale=card_scale)
    
    elif round_status in ["waiting_for_choices", "choice_made"]:
        draw_text_with_shadow(game_message, font_small, WHITE, sw / 2, content_start_y)
        if is_large_screen:
            height_ratio = sh / SCREEN_HEIGHT
            card_scale = 1.0 + (height_ratio - 1.0) * 1.5
            card_scale = max(0.8, card_scale)
            card_spacing = sw / 3.5
            card_y_pos = sh * 0.55
        else:
            card_scale = 1.0
            card_spacing = 220
            card_y_pos = sh * 0.58
        num_cards = len(player_hand)
        total_hand_width = (num_cards - 1) * card_spacing
        start_x = (sw / 2) - (total_hand_width / 2)
        for i, card_data in enumerate(player_hand):
            is_selected = (player_choice == card_data)
            card_x_pos = start_x + i * card_spacing
            card_rect = draw_card_as_image_button(card_x_pos, card_y_pos, card_data, is_selected, is_clickable=True, extra_scale=card_scale)
            card_data["rect"] = card_rect
    
def send_message(message_type, data):
    global connected_to_server
    if not connected_to_server: return
    try:
        pickled_data = pickle.dumps({"type": message_type, "data": data})
        client_socket.sendall(f"{len(pickled_data):<{HEADER_LENGTH}}".encode('utf-8') + pickled_data)
    except socket.error as e:
        print(f"Failed to send message: {e}")
        connected_to_server = False

def receive_messages():
    global player_id, game_message, player_hps, round_status, game_over, player_hand, connected_to_server
    global revealed_player_card_data, revealed_opponent_card_data, local_player_won, end_screen_animation_active, end_screen_text_velocity, player_names, username, last_known_hps, end_screen_text_scale
    full_msg, new_msg = b'', True
    while connected_to_server:
        try:
            chunk = client_socket.recv(4096)
            if not chunk: connected_to_server = False; break
            full_msg += chunk
            while True:
                if new_msg:
                    if len(full_msg) < HEADER_LENGTH: break
                    msg_len = int(full_msg[:HEADER_LENGTH]); new_msg = False
                if len(full_msg) - HEADER_LENGTH < msg_len: break
                
                data_object = pickle.loads(full_msg[HEADER_LENGTH : HEADER_LENGTH + msg_len])
                msg_type, msg_data = data_object.get("type"), data_object.get("data")
                
                if msg_type == "player_id":
                    player_id = msg_data["id"]
                elif msg_type == "player_update":
                    game_message = msg_data["message"]
                    if "usernames" in msg_data: player_names = msg_data["usernames"]
                elif msg_type == "game_state":
                    game_message, player_hps, round_status = msg_data["message"], msg_data["hps"], msg_data["round_status"]
                    if "usernames" in msg_data: player_names = msg_data["usernames"]
                    
                    # When server puts us back in 'entering_username', reset the game over state
                    if round_status == "entering_username": 
                        username = ""
                        game_over = False 
                        end_screen_animation_active = False
                    
                    player_hand = [dict(card, current_scale=NORMAL_SCALE, current_tilt=0) for card in msg_data.get("player_hand", [])]
                    if round_status in ["waiting_for_choices", "waiting_for_players"]:
                        player_choice, revealed_player_card_data, revealed_opponent_card_data = None, None, None
                
                elif msg_type == "round_result":
                    new_hps = msg_data["hps"]
                    for p_id_key in range(2):
                        if new_hps.get(p_id_key, INITIAL_HP) < last_known_hps.get(p_id_key, INITIAL_HP):
                            hp_shake_info[p_id_key]["is_shaking"] = True
                            hp_shake_info[p_id_key]["duration"] = 15
                    last_known_hps = new_hps.copy()
                    
                    player_hps, round_status, game_over = msg_data["hps"], msg_data["round_status"], msg_data.get("game_over", False)
                    if "usernames" in msg_data: player_names = msg_data["usernames"]
                    game_message = msg_data["message"] 
                    
                    if game_over and not end_screen_animation_active:
                        if player_id is not None:
                            win_string = f"{player_names.get(player_id)} wins the game!"
                            local_player_won = win_string in game_message
                        
                        end_screen_text_scale = 0.0
                        end_screen_text_velocity = 0.0
                        end_screen_animation_active = True
                        
                    revealed_player_card_data = msg_data["player0_choice"] if player_id == 0 else msg_data["player1_choice"]
                    revealed_opponent_card_data = msg_data["player1_choice"] if player_id == 0 else msg_data["player0_choice"]
                
                full_msg = full_msg[HEADER_LENGTH + msg_len:]; new_msg = True
                if not full_msg: break
        except (socket.error, pickle.UnpicklingError, EOFError, ValueError, IndexError) as e:
            print(f"Error in receive thread: {e}")
            connected_to_server = False; break

def game_loop():
    global connected_to_server, player_choice, round_status, game_message, game_over, end_screen_text_scale, end_screen_text_velocity
    global screen, fullscreen, username, input_box_active
    try:
        client_socket.connect((SERVER_HOST, SERVER_PORT))
        connected_to_server = True
        threading.Thread(target=receive_messages, daemon=True).start()
    except socket.error as e:
        game_message = "Could not connect to server."; connected_to_server = False
    
    running, clock = True, pygame.time.Clock()
    shake_offsets = {0: (0, 0), 1: (0, 0)}
    
    while running:
        sw, sh = screen.get_width(), screen.get_height()
        mouse_pos = pygame.mouse.get_pos()
        
        for p_id, info in hp_shake_info.items():
            if info["is_shaking"]:
                if info["duration"] > 0:
                    info["duration"] -= 1
                    dx = random.randint(-info["intensity"], info["intensity"])
                    dy = random.randint(-info["intensity"], info["intensity"])
                    shake_offsets[p_id] = (dx, dy)
                else:
                    info["is_shaking"] = False
                    shake_offsets[p_id] = (0,0)
                    
        if game_over and end_screen_animation_active:
            target_scale = 1.0; force = (target_scale - end_screen_text_scale) * spring
            end_screen_text_velocity = (end_screen_text_velocity + force) * damping
            end_screen_text_scale += end_screen_text_velocity
            
        for card_data in player_hand:
            is_hovered = "rect" in card_data and card_data.get("rect") and card_data["rect"].collidepoint(mouse_pos)
            target_scale = HOVER_SCALE if is_hovered or player_choice == card_data else NORMAL_SCALE
            target_tilt = TILT_ANGLE if player_choice == card_data else 0
            card_data["current_scale"] += (target_scale - card_data["current_scale"]) * SCALE_SPEED
            card_data["current_tilt"] += (target_tilt - card_data["current_tilt"]) * TILT_SPEED
            
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            if event.type == pygame.VIDEORESIZE:
                if not fullscreen: screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
            if event.type == pygame.KEYDOWN and event.key == pygame.K_F11:
                fullscreen = not fullscreen
                screen = pygame.display.set_mode((0, 0) if fullscreen else (SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
            
            if round_status == "entering_username":
                if event.type == pygame.MOUSEBUTTONDOWN:
                    input_pos_x, input_pos_y = sw * 0.4, sh * 0.45
                    input_click_rect = pygame.Rect(input_pos_x - 200, input_pos_y - 50, 400, 100)
                    join_button_rect = pygame.Rect(sw / 2 - 125, sh * 0.8, 250, 70)
                    
                    input_box_active = input_click_rect.collidepoint(event.pos)

                    if join_button_rect.collidepoint(event.pos) and len(username.strip()) > 0:
                        send_message("ready", {"username": username.strip()})
                        round_status = "waiting_for_players"
                if event.type == pygame.KEYDOWN and input_box_active:
                    if event.key == pygame.K_RETURN and len(username.strip()) > 0:
                        send_message("ready", {"username": username.strip()})
                        round_status = "waiting_for_players"
                    elif event.key == pygame.K_BACKSPACE:
                        username = username[:-1]
                    elif font_large.size(username)[0] < 380: 
                        username += event.unicode
            else:
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and connected_to_server:
                    insta_win_rect = pygame.Rect(sw - 160, 10, 150, 40)
                    if not game_over and insta_win_rect.collidepoint(mouse_pos):
                        send_message("insta_win", {})
                        continue 
                    
                    # --- MODIFICATION ---
                    # Removed click handler for the rematch button as it no longer exists.

                    if round_status == "waiting_for_choices":
                        for card in player_hand:
                            if "rect" in card and card["rect"] and card["rect"].collidepoint(mouse_pos):
                                player_choice = card; send_message("choice", {"choice": card}); round_status = "choice_made"; game_message = "Choice locked in! Waiting..."; break
        
        draw_game_screen(sw, sh, shake_offsets) 
        pygame.display.flip()
        clock.tick(60)
        
    if connected_to_server: client_socket.close()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    game_loop()