# CLIENT CODE
import socket
import threading

HOST = "127.0.0.1"
PORT = 1234

username = ""  # Will be set later


def listen_for_messages(client):
    while True:
        try:
            message = client.recv(2048).decode("utf-8")
            if message:
                if "~" in message:
                    sender, content = message.split("~", 1)
                    print(f"[{sender}] - {content}")
                else:
                    print(message)
        except:
            print("Disconnected from server.")
            break


def send_messages(client):
    while True:
        msg = input("")
        if msg.strip() != "":
            client.sendall(f"{username}~{msg}".encode())
        else:
            print("Empty message not allowed.")


def main():
    global username

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client.connect((HOST, PORT))
        print("Connected to server.")
    except:
        print("Could not connect.")
        return

    username = input("Enter username: ").strip()
    if username == "":
        print("Username cannot be empty.")
        return

    # Send username to server
    client.sendall(username.encode())

    # Start listening thread
    threading.Thread(target=listen_for_messages, args=(client,), daemon=True).start()

    # Start sending messages
    send_messages(client)


if __name__ == "__main__":
    main()
