import socket
import threading
from datetime import datetime


HOST = "127.0.0.1"
PORT = 1234
MAX_CLIENTS = 20

# username -> socket
clients: dict[str, socket.socket] = {}
clients_lock = threading.Lock()


def timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def send_line(client_socket: socket.socket, message: str) -> bool:
    """
    Send one newline-terminated message.
    Returns False if sending fails.
    """
    try:
        client_socket.sendall((message + "\n").encode("utf-8"))
        return True
    except OSError:
        return False


def find_username(requested_username: str) -> str | None:
    """
    Find a connected username without case sensitivity.
    """
    with clients_lock:
        for username in clients:
            if username.lower() == requested_username.lower():
                return username

    return None


def get_usernames() -> list[str]:
    with clients_lock:
        return sorted(clients.keys(), key=str.lower)


def send_user_list_to_everyone() -> None:
    usernames = get_usernames()
    message = "USERS|" + ",".join(usernames)
    broadcast(message)


def broadcast(
    message: str,
    excluded_socket: socket.socket | None = None
) -> None:
    """
    Send a message to all connected clients.
    """
    failed_users: list[str] = []

    with clients_lock:
        clients_snapshot = list(clients.items())

    for username, client_socket in clients_snapshot:
        if client_socket == excluded_socket:
            continue

        if not send_line(client_socket, message):
            failed_users.append(username)

    for username in failed_users:
        remove_client(username, announce=True)


def remove_client(username: str, announce: bool = True) -> None:
    client_socket = None

    with clients_lock:
        client_socket = clients.pop(username, None)

    if client_socket is None:
        return

    try:
        client_socket.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass

    try:
        client_socket.close()
    except OSError:
        pass

    print(f"[{timestamp()}] {username} disconnected.")

    if announce:
        broadcast(f"SYSTEM|{username} left the chat.")
        send_user_list_to_everyone()


def send_help(client_socket: socket.socket) -> None:
    help_message = (
        "Available commands:\n"
        "/help - Show this help message\n"
        "/list - Show online users\n"
        "/msg username message - Send a private message\n"
        "/quit - Leave the chat"
    )

    send_line(client_socket, f"SYSTEM|{help_message}")


def send_online_users(client_socket: socket.socket) -> None:
    usernames = get_usernames()

    if usernames:
        message = (
            f"Online users ({len(usernames)}): "
            + ", ".join(usernames)
        )
    else:
        message = "No users are currently online."

    send_line(client_socket, f"SYSTEM|{message}")


def send_private_message(
    sender: str,
    client_socket: socket.socket,
    command: str
) -> None:
    parts = command.split(" ", 2)

    if len(parts) < 3:
        send_line(
            client_socket,
            "ERROR|Usage: /msg username message"
        )
        return

    requested_username = parts[1].strip()
    message = parts[2].strip()

    if not requested_username or not message:
        send_line(
            client_socket,
            "ERROR|Usage: /msg username message"
        )
        return

    recipient_username = find_username(requested_username)

    if recipient_username is None:
        send_line(
            client_socket,
            f"ERROR|User '{requested_username}' is not online."
        )
        return

    with clients_lock:
        recipient_socket = clients.get(recipient_username)

    if recipient_socket is None:
        send_line(
            client_socket,
            f"ERROR|User '{requested_username}' is not online."
        )
        return

    current_time = timestamp()

    delivered = send_line(
        recipient_socket,
        (
            f"PRIVATE_IN|{current_time}|"
            f"{sender}|{message}"
        )
    )

    if not delivered:
        remove_client(recipient_username, announce=True)

        send_line(
            client_socket,
            f"ERROR|Could not send the message to {recipient_username}."
        )
        return

    send_line(
        client_socket,
        (
            f"PRIVATE_OUT|{current_time}|"
            f"{recipient_username}|{message}"
        )
    )

    print(
        f"[{current_time}] Private: "
        f"{sender} -> {recipient_username}: {message}"
    )


def handle_command(
    username: str,
    client_socket: socket.socket,
    command: str
) -> bool:
    """
    Returns False when the client should disconnect.
    """
    lowered_command = command.lower()

    if lowered_command == "/help":
        send_help(client_socket)
        return True

    if lowered_command == "/list":
        send_online_users(client_socket)
        return True

    if lowered_command == "/quit":
        send_line(
            client_socket,
            "DISCONNECT|You disconnected from the server."
        )
        return False

    if lowered_command.startswith("/msg"):
        send_private_message(
            username,
            client_socket,
            command
        )
        return True

    send_line(
        client_socket,
        (
            f"ERROR|Unknown command: {command}. "
            "Use /help to see available commands."
        )
    )

    return True


def listen_for_messages(
    username: str,
    client_socket: socket.socket,
    reader
) -> None:
    try:
        while True:
            line = reader.readline()

            if not line:
                break

            message = line.rstrip("\n").strip()

            if not message:
                continue

            if message.startswith("/"):
                should_continue = handle_command(
                    username,
                    client_socket,
                    message
                )

                if not should_continue:
                    break

                continue

            current_time = timestamp()

            broadcast(
                f"CHAT|{current_time}|{username}|{message}"
            )

            print(
                f"[{current_time}] "
                f"{username}: {message}"
            )

    except (ConnectionResetError, OSError):
        pass

    finally:
        try:
            reader.close()
        except OSError:
            pass

        remove_client(username, announce=True)


def handle_client(
    client_socket: socket.socket,
    address: tuple[str, int]
) -> None:
    username = ""

    try:
        client_socket.settimeout(30)

        reader = client_socket.makefile(
            "r",
            encoding="utf-8",
            newline="\n"
        )

        username_line = reader.readline()

        if not username_line:
            client_socket.close()
            return

        username = username_line.rstrip("\n").strip()

        if not username:
            send_line(
                client_socket,
                "LOGIN_ERROR|Username cannot be empty."
            )
            client_socket.close()
            return

        if len(username) > 20:
            send_line(
                client_socket,
                "LOGIN_ERROR|Username must be 20 characters or fewer."
            )
            client_socket.close()
            return

        if username.startswith("/"):
            send_line(
                client_socket,
                "LOGIN_ERROR|Username cannot begin with /."
            )
            client_socket.close()
            return

        if "|" in username or "," in username:
            send_line(
                client_socket,
                "LOGIN_ERROR|Username cannot contain | or , symbols."
            )
            client_socket.close()
            return

        if find_username(username) is not None:
            send_line(
                client_socket,
                "LOGIN_ERROR|That username is already in use."
            )
            client_socket.close()
            return

        with clients_lock:
            clients[username] = client_socket
            online_count = len(clients)

        client_socket.settimeout(None)

        current_time = timestamp()

        print(
            f"[{current_time}] {username} connected from "
            f"{address[0]}:{address[1]}"
        )

        send_line(
            client_socket,
            (
                f"LOGIN_SUCCESS|Welcome, {username}! "
                f"There are {online_count} user(s) online."
            )
        )

        broadcast(
            f"SYSTEM|{username} joined the chat.",
            excluded_socket=client_socket
        )

        send_user_list_to_everyone()

        listen_for_messages(
            username,
            client_socket,
            reader
        )

    except socket.timeout:
        print(
            f"[{timestamp()}] Connection from "
            f"{address[0]}:{address[1]} timed out."
        )

        try:
            client_socket.close()
        except OSError:
            pass

    except OSError as error:
        print(
            f"[{timestamp()}] Client error from "
            f"{address[0]}:{address[1]}: {error}"
        )

        if username:
            remove_client(username, announce=True)
        else:
            try:
                client_socket.close()
            except OSError:
                pass


def shutdown_server(server_socket: socket.socket) -> None:
    print("\nShutting down server...")

    with clients_lock:
        clients_snapshot = list(clients.items())

    for username, client_socket in clients_snapshot:
        send_line(
            client_socket,
            "DISCONNECT|The server is shutting down."
        )

        remove_client(username, announce=False)

    try:
        server_socket.close()
    except OSError:
        pass

    print("Server stopped.")


def main() -> None:
    server_socket = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    server_socket.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(MAX_CLIENTS)

        print("=" * 52)
        print("           MULTI-CLIENT CHAT SERVER")
        print("=" * 52)
        print(f"Address:      {HOST}:{PORT}")
        print(f"Client limit: {MAX_CLIENTS}")
        print("Status:       Waiting for connections")
        print("=" * 52)

        while True:
            client_socket, address = server_socket.accept()

            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, address),
                daemon=True
            )
            thread.start()

    except KeyboardInterrupt:
        pass

    except OSError as error:
        print(f"Server error: {error}")

    finally:
        shutdown_server(server_socket)


if __name__ == "__main__":
    main()