import socket
import threading
import json
import time

# --- Game Configuration ---
HOST = '127.0.0.1'  # Standard loopback interface address (localhost)
PORT = 65432        # Port to listen on (non-privileged ports are > 1023)

# Rules for Rock-Paper-Scissors
# Each key beats the values in its list.
# 0: Rock, 1: Paper, 2: Scissors
RPS_RULES = {
    0: [2],  # Rock (0) beats Scissors (2)
    1: [0],  # Paper (1) beats Rock (0)
    2: [1]   # Scissors (2) beats Paper (1)
}
CHOICES = {
    0: "Rock",
    1: "Paper",
    2: "Scissors"
}

# --- Game State Variables ---
connected_players = []  # List to hold (conn, addr) for each player
player_choices = {}     # Dictionary to store choices: {player_id: choice}
player_scores = {0: 0, 1: 0} # Scores for player 0 and player 1
game_started = False
player_ready_count = 0

# --- Helper Functions ---

def broadcast_message(message_type, data):
    """
    Sends a message to all connected players.
    :param message_type: A string indicating the type of message (e.g., "game_state", "round_result").
    :param data: A dictionary containing the data to send.
    """
    message = json.dumps({"type": message_type, "data": data}) + "\n"
    for player_id, (conn, addr) in enumerate(connected_players):
        try:
            conn.sendall(message.encode('utf-8'))
        except Exception as e:
            print(f"Error broadcasting to player {player_id}: {e}")
            # Consider removing disconnected players here in a more robust system

def determine_winner(choice1, choice2):
    """
    Determines the winner of a round based on RPS rules.
    :param choice1: Integer choice of player 1.
    :param choice2: Integer choice of player 2.
    :return: 0 if player 1 wins, 1 if player 2 wins, -1 for a tie.
    """
    if choice1 == choice2:
        return -1  # Tie

    # Check if choice1 beats choice2
    if choice2 in RPS_RULES.get(choice1, []):
        return 0  # Player 0 wins
    # Check if choice2 beats choice1
    elif choice1 in RPS_RULES.get(choice2, []):
        return 1  # Player 1 wins
    else:
        # This case should ideally not be reached if rules are exhaustive
        print(f"Warning: Unexpected outcome for choices {choice1} vs {choice2}")
        return -1 # Default to tie if no clear winner based on rules

def reset_round():
    """Resets player choices for the next round."""
    global player_choices
    player_choices = {}
    print("Round reset. Waiting for new choices.")

def handle_client(conn, addr, player_id):
    """
    Handles communication with a single client.
    :param conn: The socket object for the client connection.
    :param addr: The address of the client.
    :param player_id: The assigned ID for this player (0 or 1).
    """
    global player_choices, player_scores, player_ready_count, game_started

    print(f"Connected by {addr} as Player {player_id}")
    conn.sendall(json.dumps({"type": "player_id", "data": {"id": player_id}}).encode('utf-8') + b'\n')

    # Send initial game state
    initial_state = {
        "message": f"Welcome, Player {player_id}. Waiting for another player...",
        "scores": player_scores,
        "round_status": "waiting_for_players",
        "player_count": len(connected_players)
    }
    conn.sendall(json.dumps({"type": "game_state", "data": initial_state}).encode('utf-8') + b'\n')

    try:
        while True:
            data = conn.recv(1024)
            if not data:
                print(f"Client {addr} disconnected.")
                break

            # Decode and process incoming messages
            messages = data.decode('utf-8').strip().split('\n')
            for msg_str in messages:
                if not msg_str:
                    continue
                try:
                    message = json.loads(msg_str)
                    msg_type = message.get("type")
                    msg_data = message.get("data")

                    if msg_type == "choice" and "choice" in msg_data:
                        if game_started and player_id not in player_choices:
                            player_choices[player_id] = msg_data["choice"]
                            print(f"Player {player_id} chose: {CHOICES[msg_data['choice']]}")

                            # Check if both players have made their choice
                            if len(player_choices) == 2:
                                print("Both players have made their choices. Determining round winner...")
                                choice0 = player_choices.get(0)
                                choice1 = player_choices.get(1)

                                if choice0 is not None and choice1 is not None:
                                    winner_id = determine_winner(choice0, choice1)
                                    result_message = ""
                                    if winner_id == -1:
                                        result_message = "It's a tie!"
                                    else:
                                        player_scores[winner_id] += 1
                                        result_message = f"Player {winner_id} wins this round!"

                                    round_results = {
                                        "message": result_message,
                                        "player0_choice": CHOICES.get(choice0, "Unknown"),
                                        "player1_choice": CHOICES.get(choice1, "Unknown"),
                                        "winner": winner_id,
                                        "scores": player_scores,
                                        "round_status": "round_over"
                                    }
                                    broadcast_message("round_result", round_results)
                                    print(f"Round results broadcasted: {round_results}")
                                    reset_round() # Prepare for next round
                                else:
                                    print("Error: One or both choices were None after both players chose.")
                                    # Handle this error condition, maybe ask players to choose again
                        else:
                            print(f"Player {player_id} sent choice but game not started or already chose.")

                    elif msg_type == "ready":
                        if not game_started:
                            player_ready_count += 1
                            print(f"Player {player_id} is ready. Ready count: {player_ready_count}")
                            if player_ready_count == 2:
                                game_started = True
                                print("Both players ready. Game starting!")
                                broadcast_message("game_state", {
                                    "message": "Game started! Make your choice.",
                                    "scores": player_scores,
                                    "round_status": "waiting_for_choices"
                                })
                        else:
                            print(f"Player {player_id} sent ready but game already started.")

                    elif msg_type == "next_round":
                        # This message can be sent by clients to signal they are ready for the next round
                        # After a round is over, the server will transition to waiting_for_choices
                        # for the next round.
                        print(f"Player {player_id} requested next round.")
                        # The server implicitly handles this by resetting the round and waiting for choices.
                        # No explicit action needed here unless we want a "ready for next round" system.
                        # For now, simply making a choice starts the next round for that player.

                except json.JSONDecodeError as e:
                    print(f"Invalid JSON from {addr}: {msg_str} - {e}")
                except Exception as e:
                    print(f"Error processing message from {addr}: {e}")

    except Exception as e:
        print(f"Error with client {addr}: {e}")
    finally:
        # Clean up on disconnect
        print(f"Closing connection for Player {player_id} ({addr})")
        conn.close()
        # Remove the disconnected player from the list
        for i, (p_conn, p_addr) in enumerate(connected_players):
            if p_conn == conn:
                connected_players.pop(i)
                break
        # Reset game state if a player disconnects
        game_started = False
        player_ready_count = 0
        player_scores = {0: 0, 1: 0}
        player_choices = {}
        print("Game reset due to player disconnect.")
        broadcast_message("game_state", {
            "message": "A player disconnected. Waiting for players to reconnect...",
            "scores": player_scores,
            "round_status": "waiting_for_players",
            "player_count": len(connected_players)
        })


def start_server():
    """Starts the main game server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1) # Allow reuse of address
    server_socket.bind((HOST, PORT))
    server_socket.listen(2) # Listen for up to 2 connections (for 2 players)
    print(f"Server listening on {HOST}:{PORT}")

    # Use a simpler player ID assignment since we only have two players
    next_player_id = 0

    while True:
        if len(connected_players) < 2:
            try:
                conn, addr = server_socket.accept()
                if len(connected_players) < 2: # Double check to prevent race conditions
                    connected_players.append((conn, addr))
                    # Assign player ID and start a new thread for the client
                    thread = threading.Thread(target=handle_client, args=(conn, addr, next_player_id))
                    thread.start()
                    next_player_id = 1 if next_player_id == 0 else 0 # Alternate between 0 and 1
                    print(f"Accepted connection from {addr}. Total players: {len(connected_players)}")
                else:
                    # If somehow more than 2 players try to connect, reject
                    conn.sendall(b"Server full. Please try again later.\n")
                    conn.close()
            except Exception as e:
                print(f"Error accepting connection: {e}")
        else:
            # Server is full, just wait or do other background tasks
            time.sleep(1) # Prevent busy-waiting

if __name__ == "__main__":
    start_server()
