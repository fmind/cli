"""Select daily news editions from the news archive: newest, or matching."""

from typing import Any

type Edition = dict[str, Any]


def _edition_text(edition: Edition) -> str:
    """Return the searchable header of one edition, lower-cased: its date slug and title."""
    return f"{edition['slug']} {edition['title']}".lower()


def _item_text(item: dict[str, Any]) -> str:
    """Return the searchable text of one link, lower-cased."""
    return " ".join((item["title"], item["domain"], item["description"], item["url"])).lower()


def search(editions: list[Edition], query: str, *, limit: int) -> list[Edition]:
    """Return newest-first editions, keeping only the links that contain every term of `query`.

    Terms are ANDed, case-insensitively, against the edition header and each link,
    so `2026-11-06` selects that whole edition and `agent 2026-11` keeps November's
    agent links. Without terms, return the latest editions unchanged.
    """
    terms = query.lower().split()
    found: list[Edition] = []
    if limit <= 0:
        return found
    for edition in sorted(editions, key=lambda e: (e["date"], e["slug"]), reverse=True):
        if terms:
            header = _edition_text(edition)
            items = [
                item
                for item in edition["items"]
                if (haystack := f"{header} {_item_text(item)}") and all(t in haystack for t in terms)
            ]
        else:
            items = edition["items"]
        if items:
            found.append(edition if len(items) == len(edition["items"]) else {**edition, "items": items})
        if len(found) >= limit:
            break
    return found
