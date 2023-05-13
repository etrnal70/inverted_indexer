import os

from dotenv import load_dotenv

from src.database.database import Database
from src.indexing.inverted_index import Indexer

# TODO This will be only for testing purpose.
# Next step will hide this behind an IPC handler

if __name__ == "__main__":
    load_dotenv()
    status = str(os.getenv("INDEXER_STATUS"))
    useGST = str(os.getenv("INDEXER_USE_GST"))
    barrelMode = str(os.getenv("INDEXER_BARREL_STORE"))
    db = Database()
    idx = Indexer(db, status, useGST, barrelMode)

    try:
        if status == "reindex":
            dump = idx.getRepositoryDump()
            idx.generateIndex(dump)
            idx.sortHitlists()
            idx.storeIndex()
        elif status == "search":
            idx.prepareIndexer()

        userInput = input("Input query: ")
        idx.search(userInput)
    finally:
        idx.cleanup()
