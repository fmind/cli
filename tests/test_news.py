"""News selection: latest editions, term matching per link, and bounds."""

from collections.abc import Sequence

from fmind import news
from fmind.api import NewsArchive, NewsEdition


def slugs(editions: Sequence[NewsEdition]) -> list[str]:
    return [edition["slug"] for edition in editions]


def titles(edition: NewsEdition) -> list[str]:
    return [item["title"] for item in edition["items"]]


def test_without_terms_returns_the_latest_editions_whole(news_archive: NewsArchive) -> None:
    editions = news_archive["editions"]
    assert slugs(news.search(editions, "", limit=2)) == ["2024-08-16", "2024-08-15-summit"]
    assert news.search(editions, "", limit=1)[0] is editions[0], "an unfiltered edition is the published one"
    assert news.search(editions, "", limit=0) == []
    assert news.search(editions, "", limit=-1) == []


def test_editions_without_items_are_omitted(news_archive: NewsArchive) -> None:
    empty: NewsEdition = {**news_archive["editions"][0], "slug": "2024-08-17", "date": "2024-08-17", "items": []}
    assert slugs(news.search([empty, *news_archive["editions"]], "", limit=1)) == ["2024-08-16"]


def test_editions_are_newest_first_whatever_the_published_order(news_archive: NewsArchive) -> None:
    same_day: NewsEdition = {**news_archive["editions"][1], "slug": "2024-08-15"}
    editions: list[NewsEdition] = [same_day, *reversed(news_archive["editions"])]
    assert slugs(news.search(editions, "", limit=9)) == [
        "2024-08-16",
        "2024-08-15-summit",
        "2024-08-15",
        "2024-07-01",
    ]


def test_terms_keep_only_matching_links(news_archive: NewsArchive) -> None:
    found = news.search(news_archive["editions"], "AGENT", limit=9)
    assert slugs(found) == ["2024-08-16", "2024-08-15-summit"], "matching is case-insensitive"
    assert titles(found[0]) == ["Agents"]
    assert len(news_archive["editions"][0]["items"]) == 2, "filtering never mutates the archive"


def test_terms_match_each_field_independently(news_archive: NewsArchive) -> None:
    disjoint: NewsEdition = {
        **news_archive["editions"][0],
        "slug": "2024-09-01",
        "date": "2024-09-01",
        "title": "September Briefing",
        "items": [
            {
                "title": "HeadlineToken",
                "domain": "host-only.example",
                "description": "SummaryToken",
                "url": "https://cdn.example/path-token",
            }
        ],
    }
    editions: list[NewsEdition] = [disjoint, news_archive["editions"][2]]
    assert slugs(news.search(editions, "briefing", limit=9)) == ["2024-09-01"], "matches edition title"
    assert slugs(news.search(editions, "headlinetoken", limit=9)) == ["2024-09-01"], "matches item title"
    assert slugs(news.search(editions, "host-only.example", limit=9)) == ["2024-09-01"], "matches item domain"
    assert slugs(news.search(editions, "summarytoken", limit=9)) == ["2024-09-01"], "matches item description"
    assert slugs(news.search(editions, "path-token", limit=9)) == ["2024-09-01"], "matches item url"


def test_an_edition_date_or_topic_selects_every_link(news_archive: NewsArchive) -> None:
    found = news.search(news_archive["editions"], "2024-08-16", limit=9)
    assert slugs(found) == ["2024-08-16"]
    assert titles(found[0]) == ["Agents", "Python"]
    assert slugs(news.search(news_archive["editions"], "2024-08", limit=9)) == ["2024-08-16", "2024-08-15-summit"]
    assert slugs(news.search(news_archive["editions"], "summit", limit=9)) == ["2024-08-15-summit"]


def test_terms_are_anded_across_header_and_link(news_archive: NewsArchive) -> None:
    found = news.search(news_archive["editions"], "2024-08 agent", limit=9)
    assert [(e["slug"], titles(e)) for e in found] == [("2024-08-16", ["Agents"]), ("2024-08-15-summit", ["Keynote"])]
    assert news.search(news_archive["editions"], "agent advisory", limit=9) == [], "a second term must narrow"


def test_the_limit_counts_matching_editions(news_archive: NewsArchive) -> None:
    assert slugs(news.search(news_archive["editions"], "agent", limit=1)) == ["2024-08-16"]
