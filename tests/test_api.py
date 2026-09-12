"""The document loader: caching, refresh, offline fallback, and failure modes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fmind import api


def _fail(url: str, accept: str = "application/json") -> bytes:
    raise api.FmindError("no route to host")


def test_fetches_and_caches(cache_home: Path, offline: None) -> None:
    doc = api.load_profile()
    assert doc["metadata"]["alternate_name"] == "Fmind"
    assert cache_home.exists(), "a successful fetch must populate the cache"


def test_second_call_uses_cache(cache_home: Path, offline: None, monkeypatch: pytest.MonkeyPatch) -> None:
    api.load_profile()

    def explode(url: str, accept: str = "application/json") -> bytes:
        raise AssertionError("a warm cache must not hit the network")

    monkeypatch.setattr("fmind.api._download", explode)
    assert api.load_profile()["metadata"]["name"]


def test_refresh_bypasses_cache(cache_home: Path, offline: None, monkeypatch: pytest.MonkeyPatch) -> None:
    api.load_profile()
    calls: list[str] = []

    def counted(url: str, accept: str = "application/json") -> bytes:
        calls.append(url)
        return json.dumps({"metadata": {"name": "refreshed"}}).encode()

    monkeypatch.setattr("fmind.api._download", counted)
    assert api.load_profile(refresh=True)["metadata"]["name"] == "refreshed"
    assert len(calls) == 1


def test_expired_cache_is_refetched(cache_home: Path, offline: None, monkeypatch: pytest.MonkeyPatch) -> None:
    api.load_profile()
    monkeypatch.setattr(api, "CACHE_TTL_SECONDS", 0)  # nothing on disk can be younger than zero seconds
    calls: list[str] = []

    def counted(url: str, accept: str = "application/json") -> bytes:
        calls.append(url)
        return json.dumps({"metadata": {"name": "fresh"}}).encode()

    monkeypatch.setattr("fmind.api._download", counted)
    assert api.load_profile()["metadata"]["name"] == "fresh"
    assert len(calls) == 1, "an expired cache must be refetched without --refresh"


def test_stale_cache_survives_a_network_failure(
    cache_home: Path, offline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.load_profile()
    assert cache_home.exists()
    monkeypatch.setattr("fmind.api._download", _fail)
    # refresh forces a fetch, the fetch fails, the stale copy is still served
    assert api.load_profile(refresh=True)["metadata"]["alternate_name"] == "Fmind"


def test_network_failure_without_cache_raises(cache_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fmind.api._download", _fail)
    with pytest.raises(api.FmindError, match="no route"):
        api.load_profile()


def test_a_bad_payload_falls_back_to_the_cache(
    cache_home: Path, offline: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    api.load_profile()
    monkeypatch.setattr("fmind.api._download", lambda url, accept="": b"<html>maintenance</html>")
    assert api.load_profile(refresh=True)["metadata"]["alternate_name"] == "Fmind"


def test_rejects_a_non_portfolio_payload(cache_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fmind.api._download", lambda url, accept="": b'{"something": "else"}')
    with pytest.raises(api.FmindError, match="portfolio document"):
        api.load_profile()


def test_rejects_invalid_json(cache_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fmind.api._download", lambda url, accept="": b"<html>nope</html>")
    with pytest.raises(api.FmindError, match="did not return JSON"):
        api.load_profile()


def test_rejects_a_non_http_url() -> None:
    with pytest.raises(api.FmindError, match="http"):
        api._download("file:///etc/passwd")


def test_corrupt_cache_is_ignored(cache_home: Path, offline: None) -> None:
    cache_home.parent.mkdir(parents=True, exist_ok=True)
    cache_home.write_text("not json", encoding="utf-8")
    assert api.load_profile()["metadata"]["alternate_name"] == "Fmind"


def test_cache_path_honours_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert api.cache_path("profile.json") == tmp_path / "fmind" / "profile.json"
    monkeypatch.delenv("XDG_CACHE_HOME")
    assert api.cache_path("profile.json").is_relative_to(Path.home())


def test_article_url_follows_the_profile_origin() -> None:
    assert api.article_url("a-slug") == "https://www.fmind.dev/articles/a-slug.md"
    local = api.article_url("a-slug", profile_url="http://127.0.0.1:8080/api/profile")
    assert local == "http://127.0.0.1:8080/articles/a-slug.md"


@pytest.mark.parametrize("slug", ["../../etc/passwd", "a/b", "Upper", "", "a--b", "-lead", "trail-"])
def test_article_url_rejects_anything_that_is_not_a_slug(slug: str) -> None:
    with pytest.raises(api.FmindError, match="not an article slug"):
        api.article_url(slug)


def test_article_is_fetched_and_cached(cache_home: Path, offline: None) -> None:
    assert "The body of the article." in api.load_article("newer")
    assert (cache_home.parent / "articles" / "newer.md").exists()


def test_article_rejects_an_html_error_page(cache_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fmind.api._download", lambda url, accept="": b"<!doctype html><p>404")
    with pytest.raises(api.FmindError, match="did not return Markdown"):
        api.load_article("newer")


def test_oversized_response_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Response:
        def read(self, size: int) -> bytes:
            return b"x" * size

        def __enter__(self) -> _Response:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda request, timeout=0: _Response())
    with pytest.raises(api.FmindError, match="more than"):
        api._download("https://example.invalid/x")
