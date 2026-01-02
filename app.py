from rich.console import Console
from prompt_toolkit import print_formatted_text
from prompt_toolkit.formatted_text import ANSI
from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from textual.app import App
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, ListView, ListItem, Input, Button, Label
from textual.screen import ModalScreen
from textual.reactive import reactive
from models import User
from dataclasses import dataclass
from typing import Optional
import transport
import asyncio


# =============================================

title = """▄▖     ▌▄▖▖▖
▚ █▌▛▌▛▌▄▌▌▌
▄▌▙▖▌▌▙▌▙▖▙▌"""

@dataclass
class UsernameServerResult:
    user: User
    client: Optional[transport.Client]
    server: Optional[transport.Server]

class StartingModal(ModalScreen[bool | None]):
    CSS_PATH = "styles.css"

    BINDINGS = [
        ("escape", "cancel", "Cancel")
    ]
    
    def compose(self):
        yield Vertical(
            Label("- Send2U -\nSimple FIle Sharing and Chatroom App", id="title"),
            ListView(
                ListItem(Static("Create A Room"), id="create-room"),
                ListItem(Static("Join a Room"), id="join-room"),
                id="option-menu",
            ),
            id="opt-container"
        )
    
    def action_cancel(self):
        self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected):
        if event.item.id == "create-room":
            self.dismiss(True)
        else:
            self.dismiss(False)

class UsernameServerModal(ModalScreen[UsernameServerResult | None]):
    def __init__(self, run_server: bool):
        super().__init__()
        self.user = User(None, None, run_server, None)
        self.client = transport.Client()
        self.server = transport.Server() if run_server else None
        if self.server:
            self.user.ip = self.server.ip

    CSS_PATH = "styles.css"

    BINDINGS = [
        ("enter", "confirm", "Confirm"),
        ("escape", "cancel", "Cancel")
    ]
    
    def compose(self):
        if self.user.server_owner:
            yield Vertical(
                Label("Enter your username", id="modal-title"),
                Input(placeholder="Username", id="username-input"),
                id="opt-container"
            )
        else:
            yield Vertical(
                Label("Enter your username and server IP", id="title"),
                Input(placeholder="Username", id="username-input"),
                Input(placeholder="Server IP", id="server-ip-input"),
                id="opt-container"
            )

    def on_mount(self):
        self.query_one("#username-input").focus()
    
    def confirm(self):
        uname = self.query_one("#username-input", Input).value
        self.user.username = uname

        if self.user.server_owner:
            server_ip = self.user.ip
        else:
            server_ip = self.query_one("#server-ip-input", Input).value
        self.user.connected_to = server_ip
    

        if not uname:
            self.notify("Please enter your username")
        if not server_ip:
            self.notify("Please enter the server IP")
        if uname and server_ip:
            self.dismiss(UsernameServerResult(self.user, self.client, self.server))
    
    def cancel(self):
        self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted):
        self.confirm()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "confirm":
            self.confirm()
        elif event.button.id == "cancel":
            self.cancel()

    def action_confirm(self):
        self.confirm()
    
    def action_cancel(self):
        self.cancel()
    
class Send2U(App):
    def __init__(self):
        super().__init__()
        self.user: User | None = None
        self.client: transport.Client | None = None
        self.server: transport.Server | None = None
        self.client_task : asyncio.Task | None = None
        self.server_task : asyncio.Task | None = None


    CSS_PATH = "styles.css"

    def compose(self):
        yield Static(title, id="top")
        yield Horizontal(
            Vertical(
                ListView(id="message"),
                Horizontal(
                    Input(id="message_input", placeholder="Enter Message"),
                    Button("Upload Files", id="btn"),
                    id="message_container"
                ),
                id="chat"
            ),
            id="bottom"
        )
    
    def on_mount(self):
        self.push_screen(StartingModal(), self.on_confirm_starting_modal)
        self.set_interval(0.05, self._drain_incoming)

    def on_confirm_starting_modal(self, run_server: bool | None):
        if run_server != None:
            self.push_screen(UsernameServerModal(run_server=run_server), self.on_confirm_unameserver_modal)
        else:
            self.app.exit()
    
    def add_message(self, text: str):
        msg_area = self.query_one("#message", ListView)
        msg_area.append(ListItem(Static(text)))

    async def on_confirm_unameserver_modal(self, result: UsernameServerResult | None):
        if not result:
            self.app.exit()
            return
    
        self.user = result.user
        self.client = result.client
        self.server = result.server
        
        if self.server:
            self.server_task = asyncio.create_task(self.server.start_server())
            self.notify(f"Server IP: {self.server.ip}")
        self.client_task = asyncio.create_task(self.client.connect_to_server(self.user.connected_to, self.user.username))

    async def _drain_incoming(self):
        if not self.client:
            return
        while not self.client.incoming.empty():
            msg = await self.client.incoming.get()
            self.add_message(msg)

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id != "message_input":
            return
        text = event.value.strip()
        if not text or not self.client:
            return
        await self.client.send(text)
        event.input.value = ""
        

if __name__ == "__main__":
    Send2U().run()

# ====================================================
