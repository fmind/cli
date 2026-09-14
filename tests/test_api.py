"""Live-only fetching, website input validation, and transport failures."""

from __future__ import annotations

import http.client
import io
import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from fmind import api


def test_every_call_fetches_the_current_profile(offline: None, document: dict[str, Any]) -> None:
    assert api.load_profile() == document
    document["experience"][0]["company"] = "Changed upstream"
    assert api.load_profile()["experience"][0]["company"] == "Changed upstream"


def test_old_cache_is_never_used_or_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, offline: None, document: dict[str, Any]
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    old_cache = tmp_path / "fmind" / "profile.json"
    old_cache.parent.mkdir()
    old_cache.write_text('{"metadata": {"name": "obsolete"}}')
    assert api.load_profile() == document
    assert "obsolete" in old_cache.read_text()

    def fail(*args: object) -> bytes:
        raise api.FmindError("no route to host")

    monkeypatch.setattr(api, "_download", fail)
    with pytest.raises(api.FmindError, match="no route"):
        api.load_profile()


def test_environment_is_read_at_call_time(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> None:
    calls: list[str] = []

    def download(url: str, accept: str = "application/json") -> bytes:
        calls.append(url)
        return b"# Article" if accept == "text/markdown" else json.dumps(document).encode()

    monkeypatch.setattr(api, "_download", download)
    monkeypatch.setenv("FMIND_PROFILE_URL", "http://127.0.0.1:8080/api/profile/?preview=1")
    api.load_profile()
    api.load_article("newer")
    api.load_profile(url="https://example.test/api/profile")
    assert calls == [
        "http://127.0.0.1:8080/api/profile/?preview=1",
        "http://127.0.0.1:8080/articles/newer.md",
        "https://example.test/api/profile",
    ]


@pytest.mark.parametrize("payload", [b"<html>nope</html>", b"\xff", b"[" * 2000])
def test_rejects_invalid_json(payload: bytes) -> None:
    with pytest.raises(api.FmindError, match="did not return JSON"):
        api._parse_profile(payload)


@pytest.mark.parametrize("payload", [b"null", b"[]", b'{"metadata": {}}'])
def test_rejects_non_portfolio_documents(payload: bytes) -> None:
    with pytest.raises(api.FmindError, match="portfolio document"):
        api._parse_profile(payload)


@pytest.mark.parametrize(
    ("section", "value"),
    [
        ("metadata", {"name": []}),
        ("biography", [None]),
        ("experience", [{"company": "Example"}]),
        ("experience", "wrong shape"),
        ("expertise", [None]),
        ("services", None),
    ],
)
def test_rejects_malformed_sections(document: dict[str, Any], section: str, value: object) -> None:
    document[section] = value
    with pytest.raises(api.FmindError, match=f"profile.{section}"):
        api._parse_profile(json.dumps(document).encode())


@pytest.mark.parametrize(
    ("section", "key", "value"),
    [
        ("experience", "tags", [None]),
        ("certifications", "active", "false"),
        ("articles", "reading_minutes", True),
        ("articles", "date", 2026),
    ],
)
def test_rejects_invalid_nested_values(document: dict[str, Any], section: str, key: str, value: object) -> None:
    document[section][0][key] = value
    with pytest.raises(api.FmindError, match="portfolio document"):
        api._parse_profile(json.dumps(document).encode())


def test_optional_links_are_validated(document: dict[str, Any]) -> None:
    document["thesis"]["links"] = [{"label": "Missing URL"}]
    with pytest.raises(api.FmindError, match=r"thesis\.links"):
        api._parse_profile(json.dumps(document).encode())
    del document["thesis"]["links"]
    document["future_section"] = {"new": "content"}
    assert api._parse_profile(json.dumps(document).encode()) == document


def test_empty_sections_are_valid(document: dict[str, Any]) -> None:
    for key, value in document.items():
        if isinstance(value, list):
            document[key] = []
    assert api._parse_profile(json.dumps(document).encode()) == document


@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "https://",
        "http://[bad",
        "http://example.test:bad/api/profile",
        "http://example.test:99999/api/profile",
        "http://example.test/\nprofile",
        "https://user:secret@example.test/profile",
    ],
)
def test_rejects_invalid_http_urls(url: str) -> None:
    with pytest.raises(api.FmindError, match="http") as error:
        api._download(url)
    assert "secret" not in str(error.value)


def test_article_url_follows_the_profile_origin() -> None:
    assert api.article_url("a-slug") == "https://www.fmind.dev/articles/a-slug.md"
    assert api.article_url("a-slug", profile_url="http://127.0.0.1:8080/api/profile") == (
        "http://127.0.0.1:8080/articles/a-slug.md"
    )


@pytest.mark.parametrize("slug", ["../../etc/passwd", "a/b", "Upper", "", "a--b", "-lead", "trail-"])
def test_article_url_rejects_anything_that_is_not_a_slug(slug: str) -> None:
    with pytest.raises(api.FmindError, match="not an article slug"):
        api.article_url(slug)


def test_article_fetches_every_time(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter([b"# First", b"# Updated"])
    monkeypatch.setattr(api, "_download", lambda *args: next(responses))
    assert api.load_article("newer") == "# First"
    assert api.load_article("newer") == "# Updated"


@pytest.mark.parametrize("payload", [b"<!doctype html><p>404", b"", b"  "])
def test_article_rejects_empty_or_html_responses(payload: bytes) -> None:
    with pytest.raises(api.FmindError, match="did not return Markdown"):
        api._parse_markdown(payload)


def test_article_requires_utf8() -> None:
    with pytest.raises(api.FmindError, match="UTF-8"):
        api._parse_markdown(b"\xff")


def test_transport_revalidates_http_caches_and_bounds_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    def open_url(request: Any, timeout: float) -> io.BytesIO:
        assert request.get_header("Cache-control") == "no-cache"
        assert request.get_header("Accept") == "text/markdown"
        assert request.get_header("User-agent").startswith("fmind/")
        assert timeout == 15.0
        return io.BytesIO(b"# Article")

    monkeypatch.setattr("urllib.request.urlopen", open_url)
    assert api._download("https://example.test/article.md", "text/markdown") == b"# Article"
    monkeypatch.setattr(api, "MAX_BYTES", 4)
    with pytest.raises(api.FmindError, match="more than 4 bytes"):
        api._download("https://example.test/article.md", "text/markdown")


@pytest.mark.parametrize(
    "error",
    [
        urllib.error.HTTPError("https://example.test", 503, "maintenance", None, None),
        urllib.error.URLError("private transport detail"),
        TimeoutError("private timeout detail"),
        http.client.IncompleteRead(b"private partial body"),
        ValueError("private malformed URL detail"),
    ],
)
def test_transport_errors_are_safe_and_keep_the_cause(monkeypatch: pytest.MonkeyPatch, error: Exception) -> None:
    def fail(*args: object, **kwargs: object) -> bytes:
        raise error

    monkeypatch.setattr("urllib.request.urlopen", fail)
    with pytest.raises(api.FmindError) as caught:
        api._download("https://example.test/api/profile")
    assert caught.value.__cause__ is error
    assert "private" not in str(caught.value)
    if isinstance(error, urllib.error.HTTPError):
        assert "HTTP 503" in str(caught.value)
