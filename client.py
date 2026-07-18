import socket
import threading
import tkinter as tk
from queue import Empty, Queue
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText


HOST = "127.0.0.1"
PORT = 1234


class ChatClient:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Multi-Client Chat")
        self.root.geometry("900x580")
        self.root.minsize(720, 480)

        self.client_socket: socket.socket | None = None
        self.reader = None

        self.username = ""
        self.connected = False
        self.intentional_disconnect = False

        self.message_queue: Queue[str] = Queue()

        self.create_login_screen()

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close_application
        )

        self.root.after(
            100,
            self.process_message_queue
        )

    def clear_window(self) -> None:
        for widget in self.root.winfo_children():
            widget.destroy()

    def create_login_screen(self) -> None:
        self.clear_window()

        self.root.title("Multi-Client Chat - Login")

        container = tk.Frame(
            self.root,
            padx=40,
            pady=40
        )
        container.pack(expand=True)

        title_label = tk.Label(
            container,
            text="Multi-Client Chat",
            font=("Segoe UI", 25, "bold")
        )
        title_label.pack(pady=(0, 8))

        subtitle_label = tk.Label(
            container,
            text="Enter your username to join",
            font=("Segoe UI", 11)
        )
        subtitle_label.pack(pady=(0, 25))

        username_label = tk.Label(
            container,
            text="Username",
            font=("Segoe UI", 10, "bold")
        )
        username_label.pack(anchor="w")

        self.username_entry = tk.Entry(
            container,
            width=32,
            font=("Segoe UI", 12)
        )
        self.username_entry.pack(
            ipady=7,
            pady=(5, 15)
        )

        self.username_entry.focus_set()

        connect_button = tk.Button(
            container,
            text="Connect",
            width=20,
            font=("Segoe UI", 11, "bold"),
            command=self.connect_to_server
        )
        connect_button.pack(ipady=5)

        self.status_label = tk.Label(
            container,
            text="",
            font=("Segoe UI", 10)
        )
        self.status_label.pack(pady=(15, 0))

        self.username_entry.bind(
            "<Return>",
            lambda event: self.connect_to_server()
        )

    def create_chat_screen(self) -> None:
        self.clear_window()

        self.root.title(
            f"Multi-Client Chat - {self.username}"
        )

        top_frame = tk.Frame(
            self.root,
            padx=12,
            pady=10
        )
        top_frame.pack(fill="x")

        title_label = tk.Label(
            top_frame,
            text="Multi-Client Chat",
            font=("Segoe UI", 18, "bold")
        )
        title_label.pack(side="left")

        self.connection_label = tk.Label(
            top_frame,
            text=f"Connected as: {self.username}",
            font=("Segoe UI", 10)
        )
        self.connection_label.pack(side="right")

        content_frame = tk.Frame(self.root)
        content_frame.pack(
            fill="both",
            expand=True,
            padx=12
        )

        chat_frame = tk.Frame(content_frame)
        chat_frame.pack(
            side="left",
            fill="both",
            expand=True
        )

        users_frame = tk.Frame(
            content_frame,
            width=190,
            padx=10
        )
        users_frame.pack(
            side="right",
            fill="y"
        )

        users_frame.pack_propagate(False)

        online_title = tk.Label(
            users_frame,
            text="Online Users",
            font=("Segoe UI", 12, "bold")
        )
        online_title.pack(
            anchor="w",
            pady=(5, 8)
        )

        self.online_count_label = tk.Label(
            users_frame,
            text="0 online",
            font=("Segoe UI", 9)
        )
        self.online_count_label.pack(
            anchor="w",
            pady=(0, 8)
        )

        self.users_listbox = tk.Listbox(
            users_frame,
            font=("Segoe UI", 10),
            activestyle="none"
        )
        self.users_listbox.pack(
            fill="both",
            expand=True
        )

        self.users_listbox.bind(
            "<Double-Button-1>",
            self.start_private_message
        )

        self.chat_display = ScrolledText(
            chat_frame,
            wrap="word",
            state="disabled",
            font=("Segoe UI", 11),
            padx=10,
            pady=10
        )
        self.chat_display.pack(
            fill="both",
            expand=True
        )

        self.configure_text_tags()

        commands_label = tk.Label(
            self.root,
            text=(
                "Commands: /help   /list   "
                "/msg username message   /quit"
            ),
            anchor="w",
            font=("Segoe UI", 9)
        )
        commands_label.pack(
            fill="x",
            padx=14,
            pady=(6, 2)
        )

        bottom_frame = tk.Frame(
            self.root,
            padx=12,
            pady=10
        )
        bottom_frame.pack(fill="x")

        self.message_entry = tk.Entry(
            bottom_frame,
            font=("Segoe UI", 11)
        )
        self.message_entry.pack(
            side="left",
            fill="x",
            expand=True,
            ipady=7,
            padx=(0, 8)
        )

        self.send_button = tk.Button(
            bottom_frame,
            text="Send",
            width=10,
            font=("Segoe UI", 10, "bold"),
            command=self.send_message
        )
        self.send_button.pack(
            side="right",
            ipady=4
        )

        self.message_entry.bind(
            "<Return>",
            lambda event: self.send_message()
        )

        self.message_entry.focus_set()

    def configure_text_tags(self) -> None:
        self.chat_display.tag_configure(
            "timestamp",
            font=("Consolas", 9)
        )

        self.chat_display.tag_configure(
            "username",
            font=("Segoe UI", 10, "bold")
        )

        self.chat_display.tag_configure(
            "system",
            font=("Segoe UI", 10, "italic")
        )

        self.chat_display.tag_configure(
            "error",
            font=("Segoe UI", 10, "bold")
        )

        self.chat_display.tag_configure(
            "private",
            font=("Segoe UI", 10, "italic")
        )

    def connect_to_server(self) -> None:
        username = self.username_entry.get().strip()

        if not username:
            messagebox.showwarning(
                "Username Required",
                "Please enter a username."
            )
            return

        if len(username) > 20:
            messagebox.showwarning(
                "Invalid Username",
                "Username must be 20 characters or fewer."
            )
            return

        if username.startswith("/"):
            messagebox.showwarning(
                "Invalid Username",
                "Username cannot begin with /."
            )
            return

        if "|" in username or "," in username:
            messagebox.showwarning(
                "Invalid Username",
                "Username cannot contain | or , symbols."
            )
            return

        self.status_label.config(text="Connecting...")
        self.root.update_idletasks()

        try:
            self.client_socket = socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM
            )

            self.client_socket.connect((HOST, PORT))

            self.reader = self.client_socket.makefile(
                "r",
                encoding="utf-8",
                newline="\n"
            )

            self.client_socket.sendall(
                (username + "\n").encode("utf-8")
            )

            response = self.reader.readline()

            if not response:
                raise ConnectionError(
                    "The server closed the connection."
                )

            response = response.rstrip("\n")

            if response.startswith("LOGIN_ERROR|"):
                error_message = response.split("|", 1)[1]

                self.status_label.config(text="")

                messagebox.showerror(
                    "Connection Rejected",
                    error_message
                )

                self.close_socket()
                return

            if not response.startswith("LOGIN_SUCCESS|"):
                raise ConnectionError(
                    "The server returned an unexpected response."
                )

            self.username = username
            self.connected = True
            self.intentional_disconnect = False

            self.create_chat_screen()

            welcome_message = response.split("|", 1)[1]

            self.display_message(
                welcome_message,
                "system"
            )

            listener_thread = threading.Thread(
                target=self.listen_for_messages,
                daemon=True
            )
            listener_thread.start()

        except ConnectionRefusedError:
            self.status_label.config(text="")

            messagebox.showerror(
                "Connection Failed",
                "The server is not running."
            )

            self.close_socket()

        except (ConnectionError, OSError) as error:
            self.status_label.config(text="")

            messagebox.showerror(
                "Connection Error",
                f"Could not connect to the server.\n\n{error}"
            )

            self.close_socket()

    def listen_for_messages(self) -> None:
        try:
            while self.connected and self.reader:
                line = self.reader.readline()

                if not line:
                    break

                self.message_queue.put(
                    line.rstrip("\n")
                )

        except OSError:
            pass

        finally:
            if not self.intentional_disconnect:
                self.message_queue.put(
                    "CONNECTION_LOST|Connection to the server was lost."
                )

    def process_message_queue(self) -> None:
        try:
            while True:
                message = self.message_queue.get_nowait()
                self.handle_server_message(message)

        except Empty:
            pass

        self.root.after(
            100,
            self.process_message_queue
        )

    def handle_server_message(self, message: str) -> None:
        if message.startswith("CHAT|"):
            parts = message.split("|", 3)

            if len(parts) == 4:
                _, message_time, sender, content = parts

                self.display_chat_message(
                    message_time,
                    sender,
                    content
                )
            return

        if message.startswith("PRIVATE_IN|"):
            parts = message.split("|", 3)

            if len(parts) == 4:
                _, message_time, sender, content = parts

                self.display_message(
                    (
                        f"[{message_time}] "
                        f"Private from {sender}: {content}"
                    ),
                    "private"
                )
            return

        if message.startswith("PRIVATE_OUT|"):
            parts = message.split("|", 3)

            if len(parts) == 4:
                _, message_time, recipient, content = parts

                self.display_message(
                    (
                        f"[{message_time}] "
                        f"Private to {recipient}: {content}"
                    ),
                    "private"
                )
            return

        if message.startswith("SYSTEM|"):
            content = message.split("|", 1)[1]

            self.display_message(
                content,
                "system"
            )
            return

        if message.startswith("ERROR|"):
            content = message.split("|", 1)[1]

            self.display_message(
                f"Error: {content}",
                "error"
            )
            return

        if message.startswith("USERS|"):
            user_data = message.split("|", 1)[1]

            if user_data:
                usernames = user_data.split(",")
            else:
                usernames = []

            self.update_users_list(usernames)
            return

        if message.startswith("DISCONNECT|"):
            content = message.split("|", 1)[1]

            self.display_message(
                content,
                "system"
            )

            self.intentional_disconnect = True
            self.handle_disconnection()
            return

        if message.startswith("CONNECTION_LOST|"):
            if not self.intentional_disconnect:
                content = message.split("|", 1)[1]

                self.display_message(
                    content,
                    "error"
                )

                self.handle_disconnection()

    def update_users_list(self, usernames: list[str]) -> None:
        if not hasattr(self, "users_listbox"):
            return

        self.users_listbox.delete(0, tk.END)

        for username in usernames:
            display_name = username

            if username == self.username:
                display_name += " (You)"

            self.users_listbox.insert(
                tk.END,
                display_name
            )

        self.online_count_label.config(
            text=f"{len(usernames)} online"
        )

    def start_private_message(self, _event=None) -> None:
        selection = self.users_listbox.curselection()

        if not selection:
            return

        selected_text = self.users_listbox.get(
            selection[0]
        )

        selected_username = selected_text.replace(
            " (You)",
            ""
        )

        if selected_username == self.username:
            return

        self.message_entry.delete(0, tk.END)
        self.message_entry.insert(
            0,
            f"/msg {selected_username} "
        )
        self.message_entry.focus_set()
        self.message_entry.icursor(tk.END)

    def display_chat_message(
        self,
        message_time: str,
        sender: str,
        content: str
    ) -> None:
        if not hasattr(self, "chat_display"):
            return

        self.chat_display.config(state="normal")

        self.chat_display.insert(
            tk.END,
            f"[{message_time}] ",
            "timestamp"
        )

        self.chat_display.insert(
            tk.END,
            f"{sender}: ",
            "username"
        )

        self.chat_display.insert(
            tk.END,
            content + "\n"
        )

        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def display_message(
        self,
        message: str,
        tag: str | None = None
    ) -> None:
        if not hasattr(self, "chat_display"):
            return

        self.chat_display.config(state="normal")

        if tag:
            self.chat_display.insert(
                tk.END,
                message + "\n",
                tag
            )
        else:
            self.chat_display.insert(
                tk.END,
                message + "\n"
            )

        self.chat_display.see(tk.END)
        self.chat_display.config(state="disabled")

    def send_message(self) -> None:
        if not self.connected or not self.client_socket:
            messagebox.showwarning(
                "Not Connected",
                "You are not connected to the server."
            )
            return

        message = self.message_entry.get().strip()

        if not message:
            return

        try:
            self.client_socket.sendall(
                (message + "\n").encode("utf-8")
            )

            self.message_entry.delete(0, tk.END)

        except OSError:
            messagebox.showerror(
                "Send Failed",
                "The message could not be sent."
            )

            self.handle_disconnection()

    def handle_disconnection(self) -> None:
        self.connected = False

        if hasattr(self, "message_entry"):
            self.message_entry.config(state="disabled")

        if hasattr(self, "send_button"):
            self.send_button.config(state="disabled")

        if hasattr(self, "connection_label"):
            self.connection_label.config(
                text="Disconnected"
            )

        self.close_socket()

    def close_socket(self) -> None:
        self.connected = False

        if self.reader:
            try:
                self.reader.close()
            except OSError:
                pass

            self.reader = None

        if self.client_socket:
            try:
                self.client_socket.shutdown(
                    socket.SHUT_RDWR
                )
            except OSError:
                pass

            try:
                self.client_socket.close()
            except OSError:
                pass

            self.client_socket = None

    def close_application(self) -> None:
        if self.connected and self.client_socket:
            self.intentional_disconnect = True

            try:
                self.client_socket.sendall(
                    b"/quit\n"
                )
            except OSError:
                pass

        self.close_socket()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    ChatClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()