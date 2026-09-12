"""Shared fixtures: a representative profile document and an isolated cache."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

MARKDOWN = "# Newer\n\n> A summary.\n\nThe body of the article.\n"


@pytest.fixture
def document() -> dict[str, Any]:
    """A profile document with the same shape as /api/profile."""
    return {
        "metadata": {
            "name": "Médéric Hurier",
            "alternate_name": "Fmind",
            "job_title": "AI Security Architect (PhD) • Freelancer • Cyberspace",
            "headline_primary": "AI Agents, MLOps & Security",
            "email": "contact@fmind.dev",
            "site_url": "https://www.fmind.dev",
        },
        "biography": ["First paragraph.", "Second paragraph."],
        "leadership": [{"role": "Ambassador", "organization": "The Linux Foundation", "description": "d", "url": "u"}],
        "expertise": [
            {"title": "Agentic Orchestration", "emoji": "🤖", "description": "agents"},
            {"title": "Unlisted Skill", "emoji": "🔧", "description": "other"},
        ],
        "experience": [
            {
                "company": "Decathlon",
                "logo": "d.webp",
                "title": "Architect",
                "brand_color": "#000",
                "description": "current",
                "tags": ["AI/ML"],
            },
            {
                "company": "Google",
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
                "issuer": "Google Cloud",
                "cert_id": "1",
                "active": True,
            },
            {
                "url": "u",
                "logo": "l",
                "title": "ML Engineer",
                "issuer": "Google Cloud",
                "cert_id": "2",
                "active": False,
            },
        ],
        "specializations": [{"url": "u", "logo": "l", "title": "GKE", "issuer_details": "Google"}],
        "thesis": {
            "title": "Ground truth",
            "url": "u",
            "institution_details": "Uni Luxembourg, 2019",
            "description": "d",
            "links": [{"label": "Servalx", "url": "https://github.com/fmind/servalx"}],
        },
        "papers": [
            {
                "title": "Euphony",
                "url": "https://orbilu.example/euphony",
                "venue": "MSR 2017",
                "code": "https://github.com/fmind/euphony",
                "code_label": "Euphony",
            }
        ],
        "tags": [{"name": "Agent", "description": "d"}],
        "articles": [
            {
                "date": "2026-08-16",
                "updated": None,
                "title": "Newer",
                "description": "d",
                "slug": "newer",
                "url": "https://www.fmind.dev/articles/newer/",
                "image_url": "i",
                "image_alt": "a",
                "tags": ["Agent"],
                "reading_minutes": 9,
            },
            {
                "date": "2026-01-01",
                "updated": None,
                "title": "Older",
                "description": "d",
                "slug": "older",
                "url": "https://www.fmind.dev/articles/older/",
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
                "url": "https://www.fmind.dev/sites/calc/",
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
                "cta_url": "mailto:contact@fmind.dev",
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
def cache_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redirect the on-disk cache into a temporary directory."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    yield tmp_path / "fmind" / "profile.json"


@pytest.fixture
def offline(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> None:
    """Serve the fixture document instead of reaching the network."""

    def fake(url: str, accept: str = "application/json") -> bytes:
        if url.endswith(".md"):
            return MARKDOWN.encode()
        return json.dumps(document).encode()

    monkeypatch.setattr("fmind.api._download", fake)
