"""Article selection: newest first, term matching, and slug resolution."""

from __future__ import annotations

from typing import Any

from fmind import articles


def test_latest_is_newest_first_and_bounded(document: dict[str, Any]) -> None:
    assert [a["title"] for a in articles.latest(document["articles"], limit=9)] == ["Newer", "Older"]
    assert [a["title"] for a in articles.latest(document["articles"], limit=1)] == ["Newer"]
    assert articles.latest(document["articles"], limit=0) == []


def test_search_matches_title_summary_slug_and_tags(document: dict[str, Any]) -> None:
    posts = document["articles"]
    assert [a["slug"] for a in articles.search(posts, "newer")] == ["newer"]
    assert [a["slug"] for a in articles.search(posts, "AGENT")] == ["newer"], "matching is case-insensitive"
    assert [a["slug"] for a in articles.search(posts, "older")] == ["older"]


def test_search_ands_its_terms(document: dict[str, Any]) -> None:
    posts = document["articles"]
    assert articles.search(posts, "newer agent"), "both terms are present on the same article"
    assert articles.search(posts, "newer llm") == [], "a second term must narrow, not widen"


def test_search_filters_by_tag(document: dict[str, Any]) -> None:
    posts = document["articles"]
    assert [a["slug"] for a in articles.search(posts, "", tag="llm")] == ["older"]
    assert articles.search(posts, "newer", tag="LLM") == []


def test_search_respects_the_limit(document: dict[str, Any]) -> None:
    assert len(articles.search(document["articles"], "", limit=1)) == 1


def test_candidates_prefers_an_exact_slug(document: dict[str, Any]) -> None:
    posts = document["articles"] + [{"slug": "newer-still", "title": "t", "description": "d", "tags": []}]
    assert articles.candidates(posts, "newer") == ["newer"], "an exact slug is never ambiguous"
    assert articles.candidates(posts, "new") == ["newer", "newer-still"]
    assert articles.candidates(posts, "absent") == []


def test_by_slug_returns_the_index_entry(document: dict[str, Any]) -> None:
    found = articles.by_slug(document["articles"], "older")
    assert found is not None and found["title"] == "Older"
    assert articles.by_slug(document["articles"], "absent") is None
