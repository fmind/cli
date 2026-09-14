"""Shared fixtures: a synthetic profile document and offline network boundary."""

from __future__ import annotations

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
            "location": "Example City",
            "country": "EX",
            "languages": ["fr", "en"],
            "email": "alex@example.test",
            "site_url": "https://example.test",
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
            "degree": "PhD, Example Field",
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
        "tags": [{"name": "Agent", "description": "d"}],
        "articles": [
            {
                "date": "2024-08-16",
                "updated": None,
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
                "date": "2024-01-01",
                "updated": None,
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


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """An accidental real HTTP request fails the offline suite immediately."""

    def denied(*args: object, **kwargs: object) -> None:
        raise AssertionError("network access is forbidden in offline tests")

    monkeypatch.setattr("urllib.request.urlopen", denied)
    monkeypatch.setattr("httpx2.AsyncHTTPTransport.handle_async_request", denied)
    monkeypatch.delenv("FMIND_PROFILE_URL", raising=False)


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> None:
    """Serve the fixture document instead of reaching the network."""

    def fake(url: str, accept: str = "application/json") -> bytes:
        if url.endswith(".md"):
            return MARKDOWN.encode()
        return json.dumps(document).encode()

    monkeypatch.setattr("fmind.api._download", fake)
