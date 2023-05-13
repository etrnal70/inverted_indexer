import pickle
from enum import Enum
from typing import TypedDict

MSG_HEADER = bytes.fromhex("756E6A")
HEADER_KEYSET = ["command", "isEnd", "magicPacket", "scope"]

class PacketScope(Enum):
    WORD = 0b0 # Word pairs
    DOC = 0b1 # Document pairs

class PacketCommand(Enum):
    GET = 0b0 # Get data from persistence
    DUMP = 0b1 # Input data to persistence

class PacketEnd(Enum):
    F = 0b0 # False
    T = 0b1 # True

class HeaderDict(TypedDict):
    magicPacket: bytes
    isEnd: PacketEnd
    command: PacketCommand
    scope: PacketScope

def parseHeader(data: bytes) -> HeaderDict:
    h = pickle.loads(data)

    if sorted(h.keys()) != HEADER_KEYSET:
        raise ValueError(f"Got keys {h.keys()}")

    if h["magicPacket"] != MSG_HEADER:
        raise ValueError(f"magicPacket | Got {h['magicPacket']} instead")
    return {
        "magicPacket": h["magicPacket"],
        "isEnd": h["isEnd"],
        "command": h["command"],
        "scope": h["scope"]
    }
