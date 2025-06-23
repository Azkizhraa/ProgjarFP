import socket
import threading
import pickle
import time
import random

# --- Game Configuration ---
HOST = '0.0.0.0'
PORT = 65432
HEADER_LENGTH = 10
RPS_RULES = {0: [2], 1: [0], 2: [1]}
CHOICES = {0: "Rock", 1: "Paper", 2: "Scissors"}
INITIAL_HP = 100
BASE_DAMAGE_PER_ROUND = 10
NUM_CARDS_IN_HAND = 3

ALL_POSSIBLE_CARDS = [
    {"rps_value": 0, "effect": "none"},
    {"rps_value": 1, "effect": "none"},
    {"rps_value": 2, "effect": "none"},
    {"rps_value": 0, "effect": "power_attack"},
    {"rps_value": 1, "effect": "power_attack"},
    {"rps_value": 2, "effect": "power_attack"},
    {"rps_value": 0, "effect": "counter_damage_5"},
    {"rps_value": 1, "effect": "counter_damage_5"},
    {"rps_value": 2, "effect": "counter_damage_5"},
]

# --- Game State Variables ---
clients = {}  # {conn: player_id}
player_data = {
    0: {"username": "Player 0", "ready": False, "hp": INITIAL_HP, "choice": None, "hand": []},
    1: {"username": "Player 1", "ready": False, "hp": INITIAL_HP, "choice": None, "hand": []}
}
game_started = False
clients_lock = threading.Lock()

# --- Networking Helper Functions ---
def send_pickled(conn, data_object):
    """Sends a pickled object with a fixed-size header."""
    try:
        pickled_data = pickle.dumps(data_object)
        header = f"{len(pickled_data):<{HEADER_LENGTH}}".encode('utf-8')
        conn.sendall(header + pickled_data)
    except (ConnectionResetError, BrokenPipeError, ConnectionAbortedError):
        pass
    except Exception as e:
        print(f"Error in send_pickled: {e}")

def broadcast(message_type, data):
    """Broadcasts a message to all connected clients using pickle."""
    message = {"type": message_type, "data": data}
    with clients_lock:
        for conn in list(clients.keys()):
            send_pickled(conn, message)

# --- Game Logic Functions ---
def deal_cards():
    """Deals a new hand of cards to each player."""
    for i in range(2):
        player_data[i]["hand"] = random.sample(ALL_POSSIBLE_CARDS, NUM_CARDS_IN_HAND)

def process_round_end():
    """Processes the round end, applying game logic."""
    global game_started

    p0, p1 = player_data[0], player_data[1]
    choice0, choice1 = p0["choice"], p1["choice"]

    if not choice0 or not choice1: return

    winner_id = -1
    if choice0["rps_value"] != choice1["rps_value"]:
        winner_id = 0 if choice1["rps_value"] in RPS_RULES.get(choice0["rps_value"], []) else 1

    result_message = ""
    game_over = False

    if winner_id == -1:
        result_message = "It's a tie! No damage dealt."
    else:
        loser_id = 1 - winner_id
        winner_name = player_data[winner_id]["username"]
        loser_name = player_data[loser_id]["username"]
        winner_choice, loser_choice = player_data[winner_id]["choice"], player_data[loser_id]["choice"]

        damage_to_loser = 20 if winner_choice.get("effect") == "power_attack" else BASE_DAMAGE_PER_ROUND
        damage_to_winner = 5 if loser_choice.get("effect") == "counter_damage_5" else 0

        player_data[loser_id]["hp"] = max(0, player_data[loser_id]["hp"] - damage_to_loser)
        player_data[winner_id]["hp"] = max(0, player_data[winner_id]["hp"] - damage_to_winner)

        result_message = f"{winner_name} wins the round! {loser_name} takes {damage_to_loser} damage."
        if damage_to_winner > 0:
            result_message += f" {winner_name} also takes {damage_to_winner} counter-damage."

    if player_data[0]["hp"] <= 0 or player_data[1]["hp"] <= 0:
        game_over = True
        winner_name_0 = player_data[0]["username"]
        winner_name_1 = player_data[1]["username"]
        if player_data[0]["hp"] <= 0 and player_data[1]["hp"] <= 0:
            result_message = "Both players knocked out! It's a draw!"
        elif player_data[0]["hp"] <= 0:
            result_message = f"{winner_name_1} wins the game!"
        else:
            result_message = f"{winner_name_0} wins the game!"

    round_results = {
        "message": result_message,
        "player0_choice": choice0,
        "player1_choice": choice1,
        "rps_winner": winner_id,
        "hps": {i: player_data[i]["hp"] for i in range(2)},
        "round_status": "game_over" if game_over else "round_over",
        "game_over": game_over,
        "usernames": {i: player_data[i]["username"] for i in range(2)}
    }
    broadcast("round_result", round_results)

    time.sleep(5)

    if game_over:
        game_started = False
        # Reset all player data for a completely new game
        for i in range(2):
            player_data[i].update({
                "ready": False, "hp": INITIAL_HP, "choice": None, 
                "hand": [], "username": f"Player {i}"
            })

        # --- MODIFICATION ---
        # Instead of going to a rematch screen, send clients back to the initial join screen.
        broadcast("game_state", {
            "message": "Game Over! Enter a name to play again.",
            "hps": {i: player_data[i]["hp"] for i in range(2)},
            "round_status": "entering_username",
            "player_hand": [],
            "usernames": {i: player_data[i]["username"] for i in range(2)}
        })
    else:
        with clients_lock:
            p0["choice"], p1["choice"] = None, None
        deal_cards()
        with clients_lock:
            for conn, pid in clients.items():
                send_pickled(conn, {
                    "type": "game_state",
                    "data": {
                        "message": "New round! Make your choice.",
                        "hps": {i: player_data[i]["hp"] for i in range(2)},
                        "round_status": "waiting_for_choices",
                        "player_hand": player_data[pid]["hand"],
                        "usernames": {i: player_data[i]["username"] for i in range(2)}
                    }
                })

def handle_disconnect(conn):
    global game_started
    with clients_lock:
        if conn in clients:
            pid = clients[conn]
            print(f"Player {pid} disconnected.")
            del clients[conn]
            
            game_started = False
            for i in range(2):
                player_data[i].update({
                    "ready": False, "hp": INITIAL_HP, "choice": None,
                    "hand": [], "username": f"Player {i}"
                })
            
            broadcast("game_state", {
                "message": "A player disconnected. Waiting for players...",
                "hps": {0: INITIAL_HP, 1: INITIAL_HP},
                "round_status": "entering_username",
                "player_hand": [],
                "usernames": {i: player_data[i]["username"] for i in range(2)}
            })

# --- Main Client Handler Thread ---
def handle_client(conn, player_id):
    global game_started
    try:
        send_pickled(conn, {"type": "player_id", "data": {"id": player_id}})
        
        full_msg, new_msg = b'', True
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            full_msg += chunk
            while True:
                if new_msg:
                    if len(full_msg) < HEADER_LENGTH:
                        break
                    msg_len = int(full_msg[:HEADER_LENGTH])
                    new_msg = False
                
                if len(full_msg) - HEADER_LENGTH < msg_len:
                    break
                
                data_object = pickle.loads(full_msg[HEADER_LENGTH : HEADER_LENGTH + msg_len])
                msg_type, msg_data = data_object.get("type"), data_object.get("data")

                if msg_type == "ready":
                    if "username" in msg_data and msg_data["username"]:
                        player_data[player_id]["username"] = msg_data["username"]
                    
                    player_data[player_id]["ready"] = True
                    print(f"Player {player_id} ({player_data[player_id]['username']}) is ready.")
                    
                    broadcast("player_update", {
                        "message": f"{player_data[player_id]['username']} is ready. Waiting for opponent...",
                        "usernames": {i: player_data[i]["username"] for i in range(2)}
                    })
                    
                    with clients_lock:
                        if len(clients) == 2 and all(p["ready"] for p in player_data.values()):
                            game_started = True
                            print("Both players ready. Game starting!")
                            time.sleep(1)
                            for i in range(2): player_data[i]["ready"] = False
                            deal_cards()
                            for c, pid in clients.items():
                                send_pickled(c, {
                                    "type": "game_state",
                                    "data": {
                                        "message": "Game started! Make your choice.",
                                        "hps": {i: player_data[i]["hp"] for i in range(2)},
                                        "round_status": "waiting_for_choices",
                                        "player_hand": player_data[pid]["hand"],
                                        "usernames": {i: player_data[i]["username"] for i in range(2)}
                                    }
                                })
                
                elif msg_type == "choice" and game_started:
                    should_process = False
                    with clients_lock:
                        if player_data[player_id]["choice"] is None: 
                            player_data[player_id]["choice"] = msg_data["choice"]
                            if all(p["choice"] is not None for p in player_data.values()):
                                should_process = True
                    if should_process:
                        time.sleep(0.5)
                        process_round_end()
                
                elif msg_type == "insta_win" and game_started:
                    opponent_id = 1 - player_id
                    with clients_lock:
                        player_data[opponent_id]['hp'] = 0
                        if player_data[player_id]['choice'] is None:
                            player_data[player_id]['choice'] = {"rps_value": 0, "effect": "none"}
                        if player_data[opponent_id]['choice'] is None:
                            player_data[opponent_id]['choice'] = {"rps_value": 2, "effect": "none"}
                    process_round_end()

                full_msg = full_msg[HEADER_LENGTH + msg_len:]
                new_msg = True
                if not full_msg:
                    break
    except Exception as e:
        print(f"Error in handle_client for Player {player_id}: {e}")
    finally:
        handle_disconnect(conn)
        conn.close()

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, PORT))
    server_socket.listen(2)
    print(f"Server listening on {HOST}:{PORT}")
    while True:
        try:
            conn, addr = server_socket.accept()
            with clients_lock:
                if len(clients) < 2:
                    current_pids = set(clients.values())
                    assigned_id = 0 if 0 not in current_pids else 1
                    clients[conn] = assigned_id
                    player_data[assigned_id].update({
                        "ready": False, "choice": None, "username": f"Player {assigned_id}"
                    })
                    print(f"Accepted connection from {addr}. Assigned Player ID: {assigned_id}.")
                    threading.Thread(target=handle_client, args=(conn, assigned_id), daemon=True).start()
                else:
                    print(f"Rejected connection from {addr}: Server is full.")
                    send_pickled(conn, {"type": "error", "data": {"message": "Server is full."}})
                    conn.close()
        except Exception as e:
            print(f"Error in server loop: {e}")

if __name__ == "__main__":
    start_server()