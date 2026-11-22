"""Article selection: newest first, term matching, and slug resolution."""

from fmind import articles
from fmind.api import Article, Profile


def test_latest_is_newest_first_and_bounded(document: Profile) -> None:
    # Chronological order intentionally opposes alphabetical slug order.
    unsorted: list[Article] = [
        {**document["articles"][1], "slug": "a-older", "date": "2024-01-01T00:00:00Z"},
        {**document["articles"][0], "slug": "z-newer", "date": "2024-08-16T00:00:00Z"},
    ]
    assert [a["slug"] for a in articles.latest(unsorted, limit=9)] == ["z-newer", "a-older"]
    assert [a["slug"] for a in articles.latest(unsorted, limit=1)] == ["z-newer"]
    assert articles.latest(unsorted, limit=0) == []
    assert articles.latest(unsorted, limit=-1) == []
    assert articles.latest([], limit=5) == []
    same_day: list[Article] = [
        {**document["articles"][0], "slug": "zeta"},
        {**document["articles"][0], "slug": "alpha"},
    ]
    assert [a["slug"] for a in articles.latest(same_day, limit=9)] == ["alpha", "zeta"]


def test_search_matches_title_summary_slug_and_tags(document: Profile) -> None:
    posts: list[Article] = [
        {
            **document["articles"][0],
            "title": "Alpha Heading",
            "description": "Beta summary text",
            "slug": "gamma-slug",
            "tags": ["DeltaTag"],
        },
        document["articles"][1],
    ]
    assert [a["slug"] for a in articles.search(posts, "alpha")] == ["gamma-slug"], "matches title"
    assert [a["slug"] for a in articles.search(posts, "beta")] == ["gamma-slug"], "matches description"
    assert [a["slug"] for a in articles.search(posts, "gamma")] == ["gamma-slug"], "matches slug"
    assert [a["slug"] for a in articles.search(posts, "DELTATAG")] == ["gamma-slug"], "matches tags case-insensitively"


def test_search_ands_its_terms(document: Profile) -> None:
    posts = document["articles"]
    assert articles.search(posts, "newer agent"), "both terms are present on the same article"
    assert articles.search(posts, "newer llm") == [], "a second term must narrow, not widen"


def test_search_filters_by_tag(document: Profile) -> None:
    posts = document["articles"]
    assert [a["slug"] for a in articles.search(posts, "", tag="llm")] == ["older"]
    assert articles.search(posts, "newer", tag="LLM") == []


def test_search_respects_the_limit(document: Profile) -> None:
    assert len(articles.search(document["articles"], "", limit=1)) == 1


def test_candidates_prefers_an_exact_slug(document: Profile) -> None:
    posts: list[Article] = [
        *document["articles"],
        {**document["articles"][0], "slug": "newer-still", "title": "t", "description": "d", "tags": []},
    ]
    assert articles.candidates(posts, "newer") == ["newer"], "an exact slug is never ambiguous"
    assert articles.candidates(posts, "new") == ["newer", "newer-still"]
    assert articles.candidates(posts, "absent") == []
    assert articles.candidates(posts, "") == [], "empty query never matches all articles"


def test_by_slug_returns_the_index_entry(document: Profile) -> None:
    found = articles.by_slug(document["articles"], "older")
    assert found is not None
    assert found["title"] == "Older"
    assert articles.by_slug(document["articles"], "absent") is None
