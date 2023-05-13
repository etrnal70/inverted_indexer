import os
import pickle
import shelve
import socket
import time
from collections import defaultdict
from heapq import nlargest
from itertools import combinations
from re import match, sub
from typing import Dict, List, Tuple, TypedDict, Union

import pymysql
import pymysql.cursors
from bitarray import bitarray
from bitarray.util import ba2int
from simphile import jaccard_similarity  #type: ignore

from src.database.database import Database  #type: ignore
from src.indexing.gst import GST

# TODO should be on crawling
FILTERED_CHAR = ['\r\n\xa0', '\\']

POSITION_MASK = 0b00000000000000000001111111111110
CAPITAL_MASK = 0b00000000000000000000000000000001

BARREL_COUNT = 128
COMMON_WORD_RATIO = 0.001
LOWER_ELIMINATION_RATIO = 0.05
UPPER_ELIMINATION_RATIO = 0.05

PARTIAL_MATCH_OCCUR_FACTOR = 15
EXACT_MATCH_FACTOR = 1

PERSISTENT_WORDPAIRS_FILE = "telusuri_wordpairs.pkl"
PERSISTENT_DOCPAIRS_FILE = "telusuri_docpairs.pkl"
GST_FILE = "telusuri_gst.pkl"
DOC_WORD_COUNT_FILE = "telusuri_docwordcount.pkl"
CAPITAL_PATTERN = '^[A-Z].*[A-Z]$'

# WordInfo: (position, isCommonWord, isCapital)
WordInfo = Tuple[int, bool, bool]
HitLists = List[int]


class GSTResult(TypedDict):
    index: int
    count: int
    query: str

class Barrel:

    __slots__ = ("lastAccessed","pairs", "isLoaded" )

    def __init__(self) -> None:
        self.pairs: Dict[str, List[int]] = {}
        self.isLoaded = False


class UserQuery:
    """Class to store user query as a parsed structure

    Store user input (string) as a group of metadata

    Attributes:
        pairs: Mapping between word and it's information
        expectedPos: Expected word position. For ranking purpose
        documentRank: Mapping between document ID and it's score
        globalModifier: Global query score modifier
        mergedHitlists: List of hits that has been merged
    """
    __slots__ = ("docPairs", "docHitlists", "wordPairs", "expectedPos",
                 "documentRank", "globalModifier", "rootHitlists",
                 "mergedHitlists", "gstResult")

    def __init__(self) -> None:
        self.docHitlists: Dict[int, HitLists] = defaultdict(list)
        self.docPairs: Dict[str, Tuple[WordInfo, HitLists]] = {}
        self.documentRank: Dict[int, float] = defaultdict(float)
        self.expectedPos: List[int] = []
        self.globalModifier: float = 1.0
        self.gstResult: List[Tuple[int, int]]
        self.mergedHitlists: HitLists = []
        self.rootHitlists: HitLists = []
        self.wordPairs: Dict[str, Tuple[WordInfo, HitLists]] = {}

    def generateExpectedPos(self):
        """ 
        Generate expected position for the query

        The position are relative to each word in the user query. Instead of
        using the expected position directly when comparing, the difference
        in the absolute position need to be computed first.

        Common words are marked as 0
        """
        data = list(sorted(self.wordPairs.values(), key=lambda x: x[0][0]))
        for i in data:
            # If common words, skip
            if not i[0][1]:
                self.expectedPos.append(i[0][0])

    def processQuery(self):
        data = list(sorted(self.wordPairs.values(), key=lambda x: x[0][0]))
        root: Tuple[List[WordInfo], HitLists] = ([], self.mergedHitlists)

        if len(data) > 1:
            for q in data:
                root[0].append(q[0])
                # Check if common
                if not q[0][1]:
                    if len(q[1]) > 0:
                        root[1].extend(q[1])

        else:
            self.mergedHitlists.extend(data[0][1])
            root = ([data[0][0]], self.mergedHitlists)

    def calculateRankingGST(self):
        if len(self.docHitlists) == 0:
            raise IndexError("""
                Unable to calculate document ranking because
                there are no document hitlist
            """)
        temp = [set(h[1]) for h in self.wordPairs.values()]

        for doc in self.docHitlists.keys():
            exactCount = 0
            pos: List[int] = [] 
            subMatch: Dict[float, int] = {}
            for i in temp:
                t = list(set(self.docHitlists[doc]).intersection(i))
                if len(t) > 0:
                    pos.extend(t)

            if len(pos) == 0:
                continue

            # Extra sort to make sure
            pos.sort()

            if len(pos) >= len(self.expectedPos):
                marked = list(set(pos).intersection(self.rootHitlists))

                curIter: List[int] = []
                maxLen = len(pos)-1
                for idx, p in enumerate(pos):
                    if p in marked or idx == maxLen:
                        if idx == maxLen:
                            curIter.append(p)

                        if len(curIter) > 0:
                            # Calculate
                            for i, item in enumerate(curIter):
                                curIter[i] = getPosition(item)

                            # Normalize
                            diff = curIter[0] - self.expectedPos[0]
                            for j, _ in enumerate(curIter):
                                curIter[j] -= diff

                            if curIter == self.expectedPos:
                                exactCount += 1
                            # If different len, then its a partial match
                            else:
                                subScore = len(pos) / len(self.expectedPos)
                                try:
                                    subMatch[subScore] += 1
                                except KeyError:
                                    subMatch[subScore] = 1


                            # Sum up calculation
                            if idx == maxLen:
                                if exactCount > 0:
                                    self.documentRank[doc] = exactCount * self.globalModifier
                                else:
                                    # For submatch, get the highest submatch occurrence
                                    # and calculate the result with the occurrence
                                    maxSubScore = max(subMatch.keys())
                                    self.documentRank[doc] = (
                                        maxSubScore +
                                        (maxSubScore / PARTIAL_MATCH_OCCUR_FACTOR *
                                         subMatch[maxSubScore])) * self.globalModifier

                            # Reset
                            curIter.clear()

                    curIter.append(p)

    def calculateRanking(self):
        if len(self.mergedHitlists) == 0:
            raise IndexError(
                "Unable to calculate document ranking because there are no hitlist"
            )
        self.mergedHitlists.sort()
        curDoc = getDocID(self.mergedHitlists[0])
        subMatch: Dict[float, int] = {}

        curIter: List[int] = []
        exactCount = 0

        for info in self.mergedHitlists:
            docID = getDocID(info)
            pos = getPosition(info)

            if info in self.rootHitlists:
                # If len are the same, chances are not a partial match
                if len(curIter) == len(self.expectedPos):
                    # Normalize curIter
                    diff = curIter[0] - self.expectedPos[0]
                    for i, _ in enumerate(curIter):
                        curIter[i] -= diff

                    # Compare to expectedPos
                    if curIter == self.expectedPos:
                        exactCount += 1
                # If different len, then its a partial match
                else:
                    subScore = len(curIter) / len(self.expectedPos)
                    try:
                        subMatch[subScore] += 1
                    except KeyError:
                        subMatch[subScore] = 1

                curIter.clear()

            if curDoc != docID:
                # Exact match exist
                if exactCount > 0:
                    self.documentRank[
                        curDoc] = exactCount * self.globalModifier * EXACT_MATCH_FACTOR
                elif len(subMatch) > 0:
                    # For submatch, get the highest submatch occurrence and
                    # calculate the result with the occurrence
                    maxSubScore = max(subMatch.keys())
                    self.documentRank[curDoc] = (
                        maxSubScore +
                        (maxSubScore / PARTIAL_MATCH_OCCUR_FACTOR *
                         subMatch[maxSubScore])) * self.globalModifier

                # Reset context
                exactCount = 0
                subMatch.clear()
                curIter.clear()
                curDoc = docID
                curIter.append(pos)
            else:
                curIter.append(pos)


class Indexer:

    __slots__ = ("db", "useGST", "documentPairs", "wordPairs", "commonWords",
                 "gst", "documentPersistence", "wordPersistence",
                 "treePersistence", "docWordCountPersistence" ,"sock",
                 "documentBlacklist", "wordDocCount")

    def __init__(self, db: Database, status: str, useGST: str,
                 barrelMode: str) -> None:
        self.commonWords: List[str] = []
        self.db = db
        self.documentBlacklist: List[int] = []
        self.wordPairs: Dict[str, List[int]] = defaultdict(
            list)  # Array / standard list
        self.wordDocCount: Dict[int, int] = {}

        if barrelMode == "remote":
            self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

        if barrelMode == "local" and status == "reindex":
            # Remove file if reindexing
            if os.path.exists(PERSISTENT_WORDPAIRS_FILE):
                os.remove(PERSISTENT_WORDPAIRS_FILE)
            if os.path.exists(DOC_WORD_COUNT_FILE):
                os.remove(DOC_WORD_COUNT_FILE)


        if status == "reindex":
            self.docWordCountPersistence = open(DOC_WORD_COUNT_FILE, 'ab' )
        else:
            self.docWordCountPersistence = open(DOC_WORD_COUNT_FILE, 'rb')

        self.wordPersistence: shelve.Shelf[Barrel] = shelve.open(
            PERSISTENT_WORDPAIRS_FILE, protocol=pickle.HIGHEST_PROTOCOL)

        if useGST == "true":
            self.useGST = True
            self.gst = GST(self.db)
            self.documentPairs: Dict[int, HitLists] = defaultdict(
                list)  # Array / standard list

            if barrelMode == "local" and status == "reindex":
                # Remove file if reindexing
                if os.path.exists(PERSISTENT_DOCPAIRS_FILE):
                    os.remove(PERSISTENT_DOCPAIRS_FILE)
                if os.path.exists(GST_FILE):
                    os.remove(GST_FILE)
                self.documentPersistence = open(PERSISTENT_DOCPAIRS_FILE, 'ab')
                self.treePersistence = open(GST_FILE, 'ab')
            elif status == "search":
                # self.documentPersistence: shelve.Shelf[List[int]] = shelve.open(
                #     PERSISTENT_DOCPAIRS_FILE, protocol=pickle.HIGHEST_PROTOCOL)
                self.documentPersistence = open(PERSISTENT_DOCPAIRS_FILE, 'rb')
                self.treePersistence = open(GST_FILE, 'rb')
        else:
            self.useGST = False

    def getRepositoryDump(self) -> List[Dict[str, Union[int, str]]]:
        print("Getting data from database...")
        start = time.perf_counter()
        conn: pymysql.Connection[
            pymysql.cursors.Cursor] = self.db.connect()  #type: ignore

        try:
            with conn.cursor(cursor=pymysql.cursors.DictCursor) as cursor:
                cursor.execute("SELECT page_id, paragraph FROM page_paragraph")
                result = cursor.fetchall()
        finally:
            conn.close()

        end = time.perf_counter()
        print(f"Time elapsed getting data from database: {end - start:0.4f}s")
        return result  #type: ignore

    def sortHitlists(self):
        start = time.perf_counter()
        print("Sorting hitlists...")

        for word, hitlists in self.wordPairs.items():
            sortHit((word, hitlists))

        end = time.perf_counter()
        print(f"Time elapsed sorting hitlists: {end - start:0.4f}s")

    def cleanup(self):
        self.wordPersistence.close()
        if self.useGST:
            self.documentPersistence.close()
            self.treePersistence.close()

    def getWords(self) -> List[str]:
        return list(self.wordPairs.keys())

    def prepareIndexer(self):
        print("Preparing indexer from persistence data...")
        start = time.perf_counter()
        for barrel in self.wordPersistence.values():
            self.wordPairs.update(barrel.pairs)
        self.wordDocCount = pickle.load(self.docWordCountPersistence)
        end = time.perf_counter()
        print(f"Time elapsed restoring hitlists: {end - start:0.8f}s")

        if self.useGST:
            docStart = time.perf_counter()
            self.documentPairs = pickle.load(self.documentPersistence)
            docEnd = time.perf_counter()
            print(
                f"Time elapsed restoring document pairs: {docEnd - docStart:0.8f}s"
            )
            treeStart = time.perf_counter()
            self.gst.tree = pickle.load(self.treePersistence)
            treeEnd = time.perf_counter()
            print(
                f"Time elapsed restoring GST structure: {treeEnd - treeStart:0.8f}s"
            )
        self.generateDocumentBlacklist(self.wordDocCount)
        self.generateCommonLists()
        print("Preparing indexer from persistence data...DONE")

    def generateIndex(self, data: List[Dict[str, Union[int, str]]]):
        start = time.perf_counter()

        if self.useGST:
            # Generate GST
            print("Generating tree...")
            self.gst.generateTree()
            print("Generating tree...DONE")

        print("Generating hitlists...")
        docMap: Dict[int, List[str]] = {}
        curDoc = int(data[0]["page_id"])
        docMap[curDoc] = []

        # Gather all paragraph as a single list value per word
        for pair in data:
            if pair["page_id"] != curDoc:
                curDoc = int(pair["page_id"])
                docMap[curDoc] = []

            docMap[curDoc].append(str(pair["paragraph"]))

        for docID, paragraphs in docMap.items():
            self.wordDocCount[docID] = self.generateHitlists(docID, paragraphs)

        # Generate document blacklist
        self.generateDocumentBlacklist(self.wordDocCount)

        # Generate list of common words
        self.generateCommonLists()

        end = time.perf_counter()
        print(f"Time elapsed creating indexes: {end - start:0.4f}s")
        return

    def generateDocumentBlacklist(self, data: Dict[int, int]):
        """generateDocumentBlacklist

        Generate document blacklist.

        Blacklisted documents are documents with 10% lowest and 10% highest
        word count throughout the indexes.

        Args:
            data: Mapping between DocID and word count for each document
        """
        start = time.perf_counter()
        print("Generating document blacklists...")
        upperLimit = len(data) * UPPER_ELIMINATION_RATIO
        len(data) * LOWER_ELIMINATION_RATIO

        self.documentBlacklist.extend(nlargest(int(upperLimit), data))
        # self.documentBlacklist.extend(nsmallest(int(lowerLimit), data))

        end = time.perf_counter()
        print(f"Time elapsed generating blacklists: {end - start:0.4f}s")

    # def storeIndexRemote(self):
    #     print("Storing indexes...")
    #     barrelSize = int(len(self.wordPairs) / 64)
    #     print(f"Barrel size: {barrelSize}")
    #     maxedOut = True
    #     firstWord = ""
    #     tempBarrel = Barrel()
    #     for k, v in sorted(self.wordPairs.items(), key=lambda x: x[0]):
    #         if maxedOut:
    #             firstWord = k
    #             maxedOut = False
    #             tempBarrel = Barrel()
    #
    #         tempBarrel.pairs[k] = v
    #
    #         if len(tempBarrel.pairs) == barrelSize:
    #             self.wordPersistence[firstWord] = tempBarrel
    #             maxedOut = True
    #
    #     if self.useGST:
    #         pickle.dump(self.documentPairs,
    #                     self.documentPersistence,
    #                     protocol=pickle.HIGHEST_PROTOCOL)
    #         pickle.dump(self.gst.tree,
    #                     self.treePersistence,
    #                     protocol=pickle.HIGHEST_PROTOCOL)
    #
    #     print("Done storing indexes")
    #     self.wordPersistence.sync()

    def storeIndex(self):
        start = time.perf_counter()
        print("Storing indexes...")
        barrelSize = int(len(self.wordPairs) / 64)
        print(f"Barrel size: {barrelSize}")
        maxedOut = True
        firstWord = ""
        tempBarrel = Barrel()
        for k, v in sorted(self.wordPairs.items(), key=lambda x: x[0]):
            if maxedOut:
                firstWord = k
                maxedOut = False
                tempBarrel = Barrel()

            tempBarrel.pairs[k] = v

            if len(tempBarrel.pairs) == barrelSize:
                self.wordPersistence[firstWord] = tempBarrel
                maxedOut = True

        pickle.dump(self.wordDocCount,
                    self.docWordCountPersistence,
                    protocol=pickle.HIGHEST_PROTOCOL)

        if self.useGST:
            pickle.dump(self.documentPairs,
                        self.documentPersistence,
                        protocol=pickle.HIGHEST_PROTOCOL)
            pickle.dump(self.gst.tree,
                        self.treePersistence,
                        protocol=pickle.HIGHEST_PROTOCOL)

        end = time.perf_counter()
        print(f"Time elapsed storing index to persistent: {end - start:0.4f}s")
        self.wordPersistence.sync()

    def generateHitlists(self, docID: int, paragraphs: List[str]) -> int:
        """Generate hitlists for docID

        Args:
            docID: Document ID
            paragraphs: List of texts in paragraph tags
        """
        sdocID = bitarray(bin(docID)[2:].zfill(19))
        wordCount = 1
        totalCount = 0
        for paragraph in paragraphs:
            # TODO
            # Stripping information might be better done in crawling process
            paragraph = sub(r'\W+', ' ', paragraph)
            # paragraph = sub('[^A-Za-z0-9 ]+', ' ', paragraph)
            for char in FILTERED_CHAR:
                paragraph = paragraph.replace(char, ' ')
            words = str(paragraph).split()

            # Strip empty or single-character word
            for word in words:
                # Skip word longer than 30 characters
                # Realistically, if there is an abnormal condition where there are
                # word longer than 30 chars, then there's a problem with filtering
                if len(word) > 30:
                    continue

                # Word limit
                if wordCount > 4094:
                    wordCount = 4095

                if word == "" or len(word) == 1:
                    continue

                isCapital = bool(match(CAPITAL_PATTERN, word))
                if not isCapital:
                    word = word.lower()

                # Merge docID, word offset and capital information
                hit = ba2int(sdocID + bitarray(bin(wordCount)[2:].zfill(12)) +
                             bitarray(bin(int(isCapital))[2:].zfill(1)))

                self.wordPairs[word].append(hit)
                if self.useGST:
                    self.documentPairs[docID].append(hit)

                wordCount += 1
                totalCount += 1

        return totalCount

    # Get documents from database
    def __getDocuments(self, query: UserQuery):
        if len(query.documentRank) == 0:
            raise IndexError(
                "Unable to get documents because document ranking mapping is empty"
            )
        docs: List[int] = []
        for data in sorted(query.documentRank.items(), key=lambda x: x[1]):
            docs.append(data[0])

        print(docs)

        conn: pymysql.Connection[
            pymysql.cursors.Cursor] = self.db.connect()  #type: ignore
        queryStr = f"SELECT id_page, title, url FROM page_information WHERE id_page IN {tuple(docs)}"

        try:
            with conn.cursor(cursor=pymysql.cursors.DictCursor) as cursor:
                cursor.execute(queryStr)
                result = cursor.fetchall()
        finally:
            conn.close()

        resDict: Dict[int, Tuple[int, float, str, str]] = {}
        for r in result:
            resDict[r["id_page"]] = (r["id_page"],
                                     query.documentRank[r["id_page"]],
                                     r["title"], r["url"])

        d: Dict[int, Tuple[int, float, str, str]] = {}
        for data in sorted(query.documentRank.items(),
                           key=lambda x: x[1],
                           reverse=True):
            d[data[0]] = resDict[data[0]]

        return d

    def __parseInput(self, input: str) -> Dict[str, WordInfo]:
        infoPairs: Dict[str, WordInfo] = {}

        # Split input query by space
        words = input.split()

        # Mark position, common words and capital status
        for i, word in enumerate(words):
            isCapital = bool(match(CAPITAL_PATTERN, word))
            if not isCapital:
                word = word.lower()
            # Pos should start at 1, hence the +1
            infoPairs[word] = (i + 1, word in self.commonWords, isCapital)
        return infoPairs

    def __getInputPairs(self, query: UserQuery, infoPairs: Dict[str,
                                                                WordInfo]):
        for word in infoPairs.keys():
            # Skip storing hitlists if it's a common word
            if not infoPairs[word][1]:
                # Check if word is exist in lexicon
                try:
                    query.wordPairs[word] = (infoPairs[word],
                                             self.wordPairs[word])
                except KeyError:
                    # If capital, check if lowercase version exist
                    if infoPairs[word][2]:
                        lowerVer = word.lower()
                        if lowerVer in self.wordPairs.keys():
                            query.wordPairs[lowerVer] = (
                                infoPairs[word], self.wordPairs[lowerVer])
                            continue

                    # Find semantically nearest word with Jaccard index
                    bestMatch = self.rankSimilarity(word)
                    if len(bestMatch) == 0:
                        query.wordPairs[word] = (infoPairs[word], [])
                    else:
                        # Use word with highest similarity
                        for m in bestMatch:
                            if m[0] in self.commonWords:
                                continue

                            query.wordPairs[m[0]] = ((infoPairs[word][0],
                                                      False,
                                                      bool(
                                                          match(
                                                              CAPITAL_PATTERN,
                                                              m[0]))),
                                                     self.wordPairs[m[0]])
                            break

            else:
                query.wordPairs[word] = (infoPairs[word], [])

        # Set root hitlist. Root hitlist is the first non common word's hitlist
        for w, h in sorted(query.wordPairs.values(), key=lambda x: x[0][0]):
            if w[1]:
                continue
            query.rootHitlists = h
            break

    def __getDocumentPairs(self, query: UserQuery):
        # For GST integration:
        # 1) Get docID list of word
        # 2) Get intersection of docID between words
        # 3) Get docID hitlist
        # 4) Get word hitlist
        # 5) For each docID, get intersection between words
        # 6) Calculate diff directly
        docPairs: Dict[str, List[Tuple[int, int]]] = defaultdict(
            list)  # For (document,count)
        docList: Dict[str, List[int]] = defaultdict(list)  # For document only
        intersectPairs: Dict[float, List[int]] = defaultdict(list)
        # TODO Confirm if common word is already filtered
        for word in query.wordPairs.keys():
            # Assumptions are there will always be a result
            # since the word is found in lexicon
            docPairs[word] = self.gst.findTree(word)

        # Sort by highest count
        for val in docPairs.values():
            val.sort(key=lambda x: x[1])

        # Extract doc lists
        for k, v in docPairs.items():
            docList[k] = [d[0] for d in v]

        # TODO
        # Get intersection
        if len(docList) > 1:
            for iter in range(1, len(docList.keys())):
                for pair in combinations(docList.keys(), iter):
                    for p in pair:
                        intersectPairs[iter / len(docList.keys())] = list(
                            set(intersectPairs[iter / len(
                                docList.keys())]).intersection(docList[p]))

        # Get all docID-mapped hitlists
        storeDoc: List[int] = []
        for d in docList.values():
            storeDoc.extend(d)
        for doc in set(storeDoc):
            # Filter document blacklist
            if doc not in self.documentBlacklist:
                query.docHitlists[doc] = self.documentPairs[doc]

    def search(self, input: str) -> Dict[int, Tuple[int, float, str, str]]:
        start = time.perf_counter()
        query = UserQuery()
        infoPairs = self.__parseInput(input)
        res: Dict[int, Tuple[int, float, str, str]] = {}

        try:
            self.__getInputPairs(query, infoPairs)

            if self.useGST:
                self.__getDocumentPairs(query)

            query.generateExpectedPos()
            query.processQuery()

            if self.useGST:
                query.calculateRankingGST()
            else:
                query.calculateRanking()

                # Filter docID result based on document blacklists
                # GST-based method already filter these in query parsing step
                self.filterQuery(query)

            res = self.__getDocuments(query)
            prettyPrint(res)
        except Exception as e:
            print(f"Error on intermediate process: {e}")
        end = time.perf_counter()
        print(f"Time elapsed getting user result: {end - start:0.8f}s")

        self.wordPersistence.close()
        return res

    def filterQuery(self, query: UserQuery):
        filteredDoc: List[int] = []
        for k in query.documentRank.keys():
            if k in self.documentBlacklist:
                filteredDoc.append(k)

        for doc in filteredDoc:
            del query.documentRank[doc]

    def generateCommonLists(self):
        # TODO Accomodate this
        # if self.useGST:
        #     return
        total = int(len(self.wordPairs.keys()) * COMMON_WORD_RATIO)
        # Sort by highest count (most frequent word)
        for word, _ in sorted(self.wordPairs.items(),
                              key=lambda x: len(x[1]),
                              reverse=True):
            self.commonWords.append(word)
            if len(self.commonWords) >= total:
                break

    def rankSimilarity(self, input: str) -> List[Tuple[str, float]]:
        # TODO Accomodate this
        # if self.useGST:
        #     return []
        result: Dict[str, float] = defaultdict(float)

        for word in self.wordPairs.keys():
            result[word] = jaccard_similarity(input, word)

        return sorted(result.items(), key=lambda x: x[1], reverse=True)

    # Main loop for search service
    def listen(self):
        while True:
            try:
                pass
            except KeyboardInterrupt:
                # Cleanup whole process
                self.wordPersistence.close()
                self.documentPersistence.close()


###################
# Utility functions
###################


def getCapital(input: int) -> bool:
    return bool(input & CAPITAL_MASK)


def getPosition(input: int) -> int:
    return int((input & POSITION_MASK) / 2)


def getDocID(input: int) -> int:
    return input >> 13


def sortHit(data: Tuple[str, HitLists]):
    """sortHit

    Args:
        data: Tuple[word, histlists]

    """
    data[1].sort(reverse=True)


def prettyPrint(data: Dict[int, Tuple[int, float, str, str]], limit: int = 10):
    # By default, print only top 10
    print("\n======")
    print("RESULT")
    print("======\n")
    count = 0
    for info in data.values():
        if count == limit:
            break
        print(f"DocID: {info[0]} | Score: {info[1]}")
        print(f"Title: {info[2]}")
        print(f"URL: {info[3]}")
        print("=======================\n")

        count += 1
