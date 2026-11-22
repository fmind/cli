"""Select articles from the profile document: newest, matching, or named."""

from collections.abc import Sequence
from typing import Any

type Article = dict[str, Any]


def latest(articles: Sequence[Article], *, limit: int) -> list[Article]:
    """Return the most recently published articles, newest first."""
    by_slug = sorted(articles, key=lambda a: a["slug"])
    return sorted(by_slug, key=lambda a: a["date"], reverse=True)[: max(limit, 0)]


def _haystack(article: Article) -> str:
    """Return the searchable text of one article, lower-cased."""
    fields = [article["title"], article["description"], article["slug"], *article["tags"]]
    return " ".join(fields).lower()


def _matches(article: Article, terms: Sequence[str]) -> bool:
    if not terms:
        return True
    haystack = _haystack(article)
    return all(term in haystack for term in terms)


def search(articles: Sequence[Article], query: str, *, tag: str | None = None, limit: int = 10) -> list[Article]:
    """Return newest-first articles whose text contains every term of `query`.

    Terms are ANDed so that adding a word narrows the result, and `tag` further
    restricts to one of the site's own tags. Both comparisons are case-insensitive.
    """
    terms = query.lower().split()
    wanted = tag.lower() if tag else None
    found = [
        article
        for article in articles
        if (wanted is None or wanted in {t.lower() for t in article["tags"]}) and _matches(article, terms)
    ]
    return latest(found, limit=limit)


def candidates(articles: Sequence[Article], wanted: str) -> list[str]:
    """Return the slugs `wanted` could mean: itself when exact, else every slug containing it."""
    if not wanted:
        return []
    slugs = [article["slug"] for article in articles]
    if wanted in slugs:
        return [wanted]
    return [slug for slug in slugs if wanted in slug]


def by_slug(articles: Sequence[Article], slug: str) -> Article | None:
    """Return the article index entry for `slug`, if the profile lists it."""
    return next((article for article in articles if article["slug"] == slug), None)
