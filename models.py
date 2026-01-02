from dataclasses import dataclass
from typing import Optional

@dataclass
class User:
    username: str
    ip: str
    server_owner: bool = False
    connected_to: Optional[str] = None