# Original code by Zaidan Pratama (https://github.com/zaidanprtm/gstindexer)
# Modified by Mochammad Hanif Ramadhan:
# - Error handling on various iteration
# - Wrapper function for easier integration purpose
# - Added type annotations
# - Cleanup unused code
# - Refactor

import re
import sys
import time
from typing import List, Optional, Tuple, TypedDict, Union

import pymysql.cursors
from anytree import Node, findall_by_attr  #type: ignore

from src.database.database import Database  #type: ignore


class DBResult(TypedDict):
    id_page: int
    title: Optional[str]


class GSTResult(TypedDict):
    index: int
    count: int
    query: str


class SearchResult(TypedDict):
    query: str
    result: Node


class GST:

    __slots__ = ("db","tree")

    def __init__(self, db: Database) -> None:
        self.db = db
        self.tree = Node("root")

    def generateTree(self):
        start = time.perf_counter()
        db = self.getTitle()
        self.tree = self.makeTree(db)
        end = time.perf_counter()
        print(f"Time elapsed generating GST: {end - start:0.4f}s")


    def findTree(self, input: str) -> List[Tuple[int, int]]:
        (_, res) = self.searchTree(input)
        ranked = self.rankResult(res)
        result: List[Tuple[int, int]] = []
        for d in ranked:
            try:
                result.append((d["index"], d["count"]))
            except KeyError:
                result = [(d["index"], d["count"])]

        return result

    def getTitle(self) -> List[DBResult]:
        connection: pymysql.Connection[
            pymysql.cursors.Cursor] = self.db.connect()  #type: ignore
        with connection.cursor(cursor=pymysql.cursors.DictCursor) as cursor:
            cursor.execute("SELECT id_page, title FROM page_information")
            result = cursor.fetchall()
        for data in result:
            # menjadikan title lower case untuk dimasukkan ke tree
            if data["title"] is not None and len(data["title"]) > 0:
                data["title"] = data["title"].lower()
                # cleaning title dari simbol untuk input tree
                data["title"] = re.sub('[^A-Za-z0-9 ]+', " ",
                                       data["title"])
        return result  #type: ignore

    # addChild adalah fungsi untuk menambah anak pada tree atau membentuk GST
    def addChild(self, suf: str, parent: str, tree: Node, index: int):
        result = findall_by_attr(tree, parent, maxlevel=2)
        try:
            result = result[0]
        except StopIteration:
            # jika tidak ada node yang ditemukan
            print("No matching nodes found")
        children = result.children
        # proses add sufiks pada tree
        for child in children:
            # membandingkan sufiks yang ingin ditambah dengan node yang sudah ada apakah
            # ada substring yang sama
            status, sameString, parentNameCut, sufCut = compare_strings(
                child.name, suf)
            # jika tidak sama maka lanjut untuk dilakukan perbandingan dengan
            # node selanjutnya
            if status is False:
                continue
            # jika sudah ada substring yang sama maka akan dicek apakah sufiks
            # sudah ada atau belum pada tree
            if parentNameCut == "":
                # jika sufiks sudah ada maka tinggal tambahkan id title di indeks sufiks
                if sufCut == "":
                    if index not in child.index:
                        child.index.append(index)
                    return tree
                return self.addChild(suf=sufCut,
                                     parent=child.name,
                                     tree=child,
                                     index=index)
            # jika sudah ada substring yang sama dan sufiksnya belum ada maka
            # akan dicek apakah substring yang sudah ada memiliki anak atau tidak
            child.name = sameString
            # jika substring yang sama tidak memiliki anak maka tinggal
            # menambahkan sufiks yang belum ada menjadi anak dari substring
            # yang sudah ada
            if child.children == []:
                Node(sufCut, parent=child, index=[index])
                Node(parentNameCut, parent=child, index=child.index)
                return tree
            # jika substring yang sama memiliki anak maka anak dari substring yang
            # lama nya harus dipisahkan dengan sufiks yang akan ditambahkan
            nodeParentCut = Node(parentNameCut, index=child.index)
            nodeParentCut.children = child.children
            nodeParentCut.parent = child
            Node(sufCut, parent=child, index=[index])
            return tree
        # penambahan sufiks pada tree jika belum ada di tree
        Node(suf, parent=result, index=[index])
        return tree

    def makeTree(self, data: List[DBResult]):
        # inisiasi root
        root = Node("root")
        for title in data:
            # pemisahan setiap kata pada title untuk diproses
            if title["title"] is not None and len(title["title"]) > 0:
                for word in title["title"].split():
                    wordIndex = title["id_page"]
                    # penambahan terminal node untuk pembentukan GST
                    word += "$"
                    # proses memasukkan tiap sufiks dari kata pada title
                    for i in range(len(word)):
                        suf = word[i:]
                        self.addChild(suf=suf,
                                      parent="root",
                                      tree=root,
                                      index=wordIndex)
        return root

    def searchTree(self, arrWord: str):
        traverse = []
        searchResult = []

        for word in arrWord.split():
            word = word.lower()
            dictResult = {"query": word, "result": ""}
            result = []
            tree = self.tree
            word += "$"

            for i in range(len(word)):
                char = word[i]
                find = search_char_in_tree(tree, char)

                if find:
                    tree = find
                    traverse.append(find)
                    result.append(find)

            dictResult["result"] = result[-1]
            searchResult.append(dictResult)
        return traverse, searchResult

    # fungsi untuk mencari sebuah karakter huruf pada tree
    def search_char_in_tree(self, node: Node, char: str) -> Union[bool, Node]:
        # pencarian huruf pada anak dari tree
        for child in node.children:
            name = child.name
            # jika ada yang sama maka kembalikan node tersebut
            if name == char or name[0] == char:
                return child
        return False

    # fungsi untuk check apakah kata muncul
    def checkList(self, index: int, arr: List[GSTResult]):
        for i in range(len(arr)):
            if arr[i]["index"] == index:
                return True, i
        return False, 0

    def rankResult(self, result: List[SearchResult]) -> List[GSTResult]:
        # inisiasi variabel untuk menyimpan index dari hasil pencarian untuk dihitung
        allListDocument: List[int] = []
        listCount: List[GSTResult] = []
        for i in result:
            allListDocument.append(i["result"].index)
        # hitung nilai count untuk setiap indeks
        for i in range(len(allListDocument)):
            for idx in allListDocument[i]:
                # cek apakah setiap kata memiliki indeks yang sama
                status, sameIdx = self.checkList(idx, listCount)
                # jika ada indeks yang sama maka tambahkan nilai count
                if len(listCount) > 0 and status is True:
                    listCount[sameIdx]["count"] += 1
                    listCount[sameIdx]["query"] += " " + result[i]["query"]
                    continue

                listCount.append({
                    "index": idx,
                    "count": 1,
                    "query": result[i]["query"]
                })

        return sorted(listCount, key=lambda d: d['count'], reverse=True)


###################
# Utility functions
###################
def compare_strings(a: Optional[str], b: Optional[str]):
    if a is None or b is None:
        return False
    size = min(len(a), len(b))
    status = False
    sameString = ""
    sufCut = ""
    parentNameCut = ""
    i = 0

    while i < size and a[i] == b[i]:  # membandingkan node dengan sufiks
        status = True
        sameString += a[i]
        # removeprefix() only exists since Python 3.9
        if sys.version_info.minor >= 9:
            parentNameCut = a.removeprefix(sameString)
            sufCut = b.removeprefix(sameString)
        else:
            parentNameCut = a[len(sameString):]
            sufCut = b[len(sameString):]
        i += 1
    return status, sameString, parentNameCut, sufCut


def search_char_in_tree(node: Node, char: str) -> Optional[Node]:
    # pencarian huruf pada anak dari tree
    for child in node.children:
        name: str = child.name
        # jika ada yang sama maka kembalikan node tersebut
        if name == char or name[0] == char:
            return child
    return None
