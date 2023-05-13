import os
import pickle
import shelve
import socket
import time
from collections import defaultdict
from typing import Dict, List

from src.indexing.protocol import (
    HeaderDict,
    PacketCommand,
    PacketEnd,
    PacketScope,
    parseHeader,
)

MANAGER_STATUS_READY = 0  # Ready to use for searching
MANAGER_STATUS_REINDEX = 1  # Empty. Need to feeded by data
MANAGER_STATUS_PREPARING = 2  # Nah

PERSISTENT_WORDPAIRS_FILE = "telusuri_wordpairs.pkl"
PERSISTENT_DOCPAIRS_FILE = "telusuri_docpairs.pkl"
SOCKET_PATH = "/tmp/telusuri.sock"

MAX_PACKET_LEN = 65536
HEADER_LEN = 156


class Barrel:

    __slots__ = ("lastAccessed","pairs", "isLoaded" )

    def __init__(self) -> None:
        self.pairs: Dict[str, List[int]] = {}
        self.isLoaded = False
        # self.documentPairs: Dict[int, List[int]] = defaultdict(list)


class BarrelManager:
    """BarrelManager - Manage persistence storage

    Persistence storage are implemented using multiple binary files (barrels),
    spread into several, fixed amount of file.

    File format are: `barrel_{baseWord}.pkl`

    Attributes:
        barrelCount: Number of total barrel
        pairs: Dictionary for mapping between huhu and hehe
        rootPath: Root directory path where barrels are/will be located
    """
    __slots__ = ("wordPairs", "documentPairs","wordPersistence", "documentPersistence",
                 "sock")

    def __init__(self, status: str) -> None:
        self.__check()

        self.wordPairs: Dict[str, List[int]] = defaultdict(list)
        self.documentPairs: Dict[int, List[int]] = defaultdict(list)
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        # Remove file if reindexing
        if status == "reindex":
            # self.status = MANAGER_STATUS_REINDEX
            if os.path.exists(PERSISTENT_WORDPAIRS_FILE):
                os.remove(PERSISTENT_WORDPAIRS_FILE)
            if os.path.exists(PERSISTENT_DOCPAIRS_FILE):
                os.remove(PERSISTENT_DOCPAIRS_FILE)

        self.wordPersistence: shelve.Shelf[Barrel] = shelve.open(
            PERSISTENT_FILE, protocol=pickle.HIGHEST_PROTOCOL)
        self.sock.bind(SOCKET_PATH)
        self.sock.listen(1)

    def dumpDocumentPairs(self):
        pass

    def dumpWordPairs(self):
        pass

    def getWordPairs(self, input: str) -> bytes:
        # TODO
        pass

    def getDocumentPairs(self, input: int) -> bytes:
        # TODO
        pass

    def loadPersistence(self):
        for barrel in self.persistence.values():
            self.pairs.update(barrel.pairs)

    def getHitlist(self, word: str):
        result: List[int] = []
        try:
            result = self.pairs[word]
        except KeyError:
            result = []

        if len(result) == 0:
            pass

    # def run(self):
    #     try:
    #         print(f"Running manager on {SOCKET_PATH}")
    #         while True:
    #             h: HeaderDict = {}
    #             buffer: List[bytes] = []
    #             conn, addr = self.sock.accept()
    #             data: bytes = bytes()
    #             while True:
    #                 data = conn.recv(MAX_PACKET_LEN)
    #                 if not data:
    #                     break
    #                 h = parseHeader(data[:HEADER_LEN])
    #                 if h["isEnd"] == PacketEnd.T:
    #                     buffer.append(data[HEADER_LEN:])
    #                     break
    #                 else:
    #                     buffer.append(data[HEADER_LEN:])
    #
    #             parsed = bytes()
    #             parsed.join(buffer)
    #             dic = pickle.loads(parsed.join(buffer))
    #
    #             if h["scope"] == PacketScope.WORD:
    #                 if h["command"] == PacketCommand.GET:
    #                 elif h["command"] == PacketCommand.DUMP:
    #             elif h["scope"] == PacketScope.DOC:
    #                 if h["command"] == PacketCommand.GET:
    #                 elif h["command"] == PacketCommand.DUMP:
    #
    #
    #             print(dic)
    #     finally:
    #         self.sock.shutdown(1)
    #         print("Shutting down Manager...")
    #         self.sock.close()
    #         self.persistence.close()
    #         print("Shutting down Manager...DONE")
    #         print("Manager has been shut down")

    def __check(self):
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
