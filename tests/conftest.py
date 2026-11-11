"""Shared fixtures: synthetic profile and news documents and an offline network boundary."""

import json
from typing import Any

import pytest

MARKDOWN = "# Newer\n\n> A summary.\n\nThe body of the article.\n"


@pytest.fixture
def document() -> dict[str, Any]:
    """A profile document with the same shape as /api/profile."""
    return {
        "metadata": {
            "name": "Alex Example",
            "alternate_name": "Example",
            "job_title": "Software Architect",
            "headline_primary": "Example expertise",
            "headline_secondary": "Example credentials",
            "work_location": "Example City",
            "email": "alex@example.test",
            "site_url": "https://example.test",
            "socials": [{"name": "Code Host", "url": "https://code.example.test/alex", "icon": "code"}],
        },
        "biography": ["First paragraph.", "Second paragraph."],
        "leadership": [{"role": "Ambassador", "organization": "Example Foundation", "description": "d", "url": "u"}],
        "expertise": [
            {"title": "Automation", "emoji": "🤖", "description": "agents"},
            {"title": "Unlisted Skill", "emoji": "🔧", "description": "other"},
        ],
        "experience": [
            {
                "company": "Current Company",
                "logo": "d.webp",
                "title": "Architect",
                "brand_color": "#000",
                "description": "current",
                "tags": ["AI/ML"],
            },
            {
                "company": "Past Company",
                "logo": "g.webp",
                "title": "Research Partner",
                "brand_color": "#000",
                "description": "past",
                "tags": ["Security"],
            },
        ],
        "certifications": [
            {
                "url": "u",
                "logo": "l",
                "title": "Cloud Architect",
                "issuer": "Cloud Provider",
                "cert_id": "1",
                "active": True,
            },
            {
                "url": "u",
                "logo": "l",
                "title": "ML Engineer",
                "issuer": "Cloud Provider",
                "cert_id": "2",
                "active": False,
            },
        ],
        "specializations": [{"url": "u", "logo": "l", "title": "Containers", "issuer_details": "Past Company"}],
        "thesis": {
            "title": "Ground truth",
            "url": "u",
            "institution_details": "Example University",
            "description": "d",
            "links": [{"label": "Code", "url": "https://example.test/thesis-code"}],
        },
        "papers": [
            {
                "title": "Example Paper",
                "url": "https://orbilu.example/example-paper",
                "venue": "Example Conference",
                "code": "https://example.test/paper-code",
                "code_label": "Example Paper",
            }
        ],
        "tags": [{"name": "Agent", "description": "d"}, {"name": "LLM", "description": "d"}],
        "articles": [
            {
                "date": "2024-08-16T00:00:00Z",
                "updated": "2024-08-16T00:00:00Z",
                "title": "Newer",
                "description": "d",
                "slug": "newer",
                "url": "https://example.test/articles/newer/",
                "image_url": "i",
                "image_alt": "a",
                "tags": ["Agent"],
                "reading_minutes": 9,
            },
            {
                "date": "2024-01-01T00:00:00Z",
                "updated": "2024-01-01T00:00:00Z",
                "title": "Older",
                "description": "d",
                "slug": "older",
                "url": "https://example.test/articles/older/",
                "image_url": "i",
                "image_alt": "a",
                "tags": ["LLM"],
                "reading_minutes": 4,
            },
        ],
        "site_pages": [
            {
                "slug": "calc",
                "title": "Calculator",
                "description": "d",
                "audience": "leaders",
                "url": "https://example.test/sites/calc/",
            }
        ],
        "open_source": [{"title": "repo", "href": "h", "description": "d"}],
        "youtube_series": [{"title": "series", "url": "u", "description": "d", "cta": "View"}],
        "services": [
            {
                "icon": "🏢",
                "title": "Advisory",
                "description": "d",
                "badge": "closed",
                "badge_type": "error",
                "cta_text": "Mail",
                "cta_url": "mailto:alex@example.test",
            },
            {
                "icon": "🎓",
                "title": "Mentoring",
                "description": "d",
                "badge": "open",
                "badge_type": "info",
                "cta_text": "Book",
                "cta_url": "https://cal.example/x",
            },
        ],
    }


@pytest.fixture
def news_archive() -> dict[str, Any]:
    """A news archive with the same shape as /api/news, newest edition first."""

    def item(title: str, domain: str, description: str) -> dict[str, str]:
        return {
            "title": title,
            "url": f"https://{domain}/{title.lower()}",
            "domain": domain,
            "description": description,
        }

    def edition(slug: str, title: str, topic: str, items: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "slug": slug,
            "date": slug[:10],
            "updated": f"{slug[:10]}T00:00:00Z",
            "title": title,
            "topic": topic,
            "description": f"{len(items)} curated links.",
            "url": f"https://example.test/news/{slug}/",
            "markdown_url": f"https://example.test/news/{slug}.md",
            "items": items,
        }

    return {
        "title": "Example news",
        "description": "Daily links.",
        "url": "https://example.test/news/",
        "feed_url": "https://example.test/news/feed.xml",
        "updated": "2024-08-16T00:00:00Z",
        "editions": [
            edition(
                "2024-08-16",
                "August 16, 2024",
                "",
                [
                    item("Agents", "agents.example", "Agent sandboxing release."),
                    item("Python", "python.example", "Interpreter release."),
                ],
            ),
            edition(
                "2024-08-15-summit",
                "Summit: August 15, 2024",
                "Summit",
                [item("Keynote", "summit.example", "Agent platform keynote.")],
            ),
            edition("2024-07-01", "July 1, 2024", "", [item("Security", "security.example", "Supply chain advisory.")]),
        ],
    }


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """An accidental real HTTP request fails the offline suite immediately."""

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr("fmind.api._OPENER.open", denied)
    monkeypatch.setattr("urllib.request.urlopen", denied)
    monkeypatch.setattr("httpx2.AsyncHTTPTransport.handle_async_request", denied)
    monkeypatch.delenv("FMIND_PROFILE_URL", raising=False)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any], news_archive: dict[str, Any]) -> None:
    """Serve the fixture documents instead of reaching the network."""

    def fake(url: str, accept: str = "application/json") -> bytes:
        if url.endswith(".md"):
            return MARKDOWN.encode()
        if url.endswith("/api/news"):
            return json.dumps(news_archive).encode()
        return json.dumps(document).encode()

    monkeypatch.setattr("fmind.api._download", fake)
