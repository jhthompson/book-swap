import json
import urllib
from typing import TypedDict


class EditionDict(TypedDict, total=False):
    key: str
    title: str


class EditionsDict(TypedDict, total=False):
    numFound: int
    start: int
    numFoundExact: bool
    docs: list[EditionDict]


class DocDict(TypedDict, total=False):
    author_key: list[str]
    author_name: list[str]
    key: str
    title: str
    editions: EditionsDict


class SearchResponseDict(TypedDict, total=False):
    numFound: int
    start: int
    numFoundExact: bool
    num_found: int
    documentation_url: str
    q: str
    offset: int | None
    docs: list[DocDict]


# example: https://openlibrary.org/search.json?q=isbn:9780063021433&fields=title,key,author_key,author_name,editions
# {
#     "numFound": 1,
#     "start": 0,
#     "numFoundExact": true,
#     "num_found": 1,
#     "documentation_url": "https://openlibrary.org/dev/docs/api/search",
#     "q": "isbn:9780063021433",
#     "offset": null,
#     "docs": [
#         {
#             "author_key": [
#                 "OL7486601A"
#             ],
#             "author_name": [
#                 "R. F. Kuang"
#             ],
#             "key": "/works/OL26443093W",
#             "title": "Babel",
#             "editions": {
#                 "numFound": 1,
#                 "start": 0,
#                 "numFoundExact": true,
#                 "docs": [
#                     {
#                         "key": "/books/OL47301869M",
#                         "title": "Babel"
#                     }
#                 ]
#             }
#         }
#     ]
# }
def search_openlibrary_by_isbn(isbn: str) -> SearchResponseDict:
    url = f"https://openlibrary.org/search.json?q=isbn:{isbn}&fields=title,key,author_key,author_name,editions"

    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())

    return SearchResponseDict(**data)


def get_book_details_from_openlibrary_search_results(
    search_data: SearchResponseDict,
) -> dict:
    if search_data.get("numFound", 0) == 0:
        return {}

    first_doc = search_data["docs"][0]

    return {
        "title": first_doc.get("title"),
        "openlibrary_author_names": first_doc.get("author_name", []),
        "openlibrary_author_ids": first_doc.get("author_key", []),
        "openlibrary_edition_id": first_doc.get("editions", {})
        .get("docs", [{}])[0]
        .get("key", "")
        .split("/")[-1],  # noqa: E501
        "openlibrary_work_id": first_doc.get("key").split("/")[-1],
    }
