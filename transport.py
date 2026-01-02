import asyncio
import socket
import rich
from models import User

DEFAULT_PORT = 42069

class Server:
    def __init__(self, port: int = DEFAULT_PORT):
        self.ip = self.get_ip()
        self.port = port
        self.devices = {} # writer: User dataclass <-- dont forget ts gng
        self.server = None

        self.username_len = 10

    def get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect("192.168.1.1", 80)
        try:
            return s.getsockname()[0]
        except:
            rich.print("[bold red] Error when getting the IP for the server[/bold red]")
        finally:
            s.close()
    
    async def broadcast(self, msg: str):
        msg += "\n"
        dead = []
        for writer, _user in self.devices.items():
            try:
                writer.write(msg.encode())
                await writer.drain()
            except:
                dead.append(writer)
        for writer in dead:
            writer.close()
            await writer.wait_closed()
            self.devices.pop(writer)
            dead.remove(writer)
        

    async def server_handler(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_addr = writer.get_extra_info("peername")[0]
        name = (await reader.readline()).decode().strip()
        self.devices[writer] = User(name, client_addr)
        await self.broadcast(f"[bold green] -- {name} joined -- [/bold green]")

        if len(name) > self.username_len:
            display_name = name[:self.username_len - 3] + "..."
        else:
            display_name = name

        while True:
            try:
                data = await reader.readline()
                if not data:
                    break

                msg = data.decode().strip()
                if msg == "exit":
                    break

                await self.broadcast(f"{name:<{self.username_len}}: {msg}")
            except:
                break
        
        writer.close()
        await writer.wait_closed()
        self.broadcast(f"[bold red] - {name} left - [/bold red]")

    async def start_server(self):
        if self.server:
            rich.print("[bold red][!] Server already running[/bold red]")
            return
        
        s = await asyncio.start_server(self.server_handler, self.ip, self.port)
        self.server = s
        async with self.server:
            await self.server.serve_forever()    

    async def stop_server(self):
        if not self.server:
            rich.print("[bold red][!] Server is not running[/bold red]")
            return
        
        for writer, _user in self.devices.items():
            try:
                writer.write(f"[bold red] Room has been closed [/bold red]")
                await writer.drain()
                writer.close()
                await writer.wait_closed()
            except:
                pass
        self.server.close()
        await self.server.wait_closed()

class Client():
    def __init__(self):
        self.writer: asyncio.StreamWriter = None
        self.reader: asyncio.StreamReader = None
        self.identity: User = None
        self.ip = self.get_ip()
        self.connected: bool = False

        self.incoming: asyncio.Queue[str] = asyncio.Queue()
        self._reader_task: asyncio.Task | None = None


    def get_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("192.168.1.1", 80))
        try:
            return s.getsockname()[0]
        except:
            rich.print("[bold red] Error when getting the IP for the server[/bold red]")
        finally:
            s.close()
    
    async def connect_to_server(self, server_ip: str, name: str):
        """This shit only handle the reader, to handle the writer use self.send() method"""
        self.reader, self.writer = await asyncio.open_connection(server_ip, Server().port)

        self.writer.write(f"{name}\n".encode())
        await self.writer.drain()

        self._reader_task = asyncio.create_task(self._read_loop())

    async def send(self, msg: str):
        self.writer.write(f"{msg}\n".encode())
        await self.writer.drain()
    
    async def get_message(self) -> str:
        data = await self.reader.readline()
        if not data:
            self.close()
        msg = data.decode().strip()
        if msg == "" or msg == "exit":
            self.close()
        return msg

    async def _read_loop(self):
        while True:
            msg = await self.get_message()
            if not msg:
                break
            await self.incoming.put(msg)

    async def close(self):
        self.writer.close()
        await self.writer.wait_closed()
