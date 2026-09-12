"""Fetch and cache the documents published by www.fmind.dev."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

from fmind import __version__

PROFILE_URL = os.environ.get("FMIND_PROFILE_URL", "https://www.fmind.dev/api/profile")
# The endpoints advertise `public, max-age=3600`; the on-disk copies honour the same window.
CACHE_TTL_SECONDS = 3600
TIMEOUT_SECONDS = 15.0
# Generous next to a ~75 KB profile and ~20 KB articles, but bounded: a hostile or
# misrouted origin must not be able to fill the cache directory.
MAX_BYTES = 8 * 1024 * 1024
USER_AGENT = f"fmind/{__version__} (+https://github.com/fmind/cli)"
# Slugs reach the URL and the cache path, so only the shape the site actually mints is accepted.
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")

T = TypeVar("T")


class FmindError(RuntimeError):
    """A document could not be obtained, or was not the document that was asked for."""


def cache_path(*parts: str) -> Path:
    """Return an on-disk cache location, honouring XDG_CACHE_HOME."""
    root = os.environ.get("XDG_CACHE_HOME")
    base = Path(root) if root else Path.home() / ".cache"
    return base.joinpath("fmind", *parts)


def article_url(slug: str, *, profile_url: str = PROFILE_URL) -> str:
    """Return the Markdown source URL of an article, on the same origin as the profile."""
    if not SLUG_PATTERN.match(slug):
        msg = f"not an article slug: {slug!r}"
        raise FmindError(msg)
    origin = profile_url.removesuffix("/api/profile").rstrip("/")
    return f"{origin}/articles/{slug}.md"


def _read_cache(path: Path, ttl: int) -> bytes | None:
    """Return the cached bytes while they are younger than `ttl`; `ttl < 0` accepts any age."""
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return None
    if ttl >= 0 and age > ttl:
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def _write_cache(path: Path, payload: bytes) -> None:
    """Persist a document, ignoring an unwritable cache directory."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(payload)
        tmp.replace(path)
    except OSError:
        pass  # a read-only cache must not break a working command


def _download(url: str, accept: str = "application/json") -> bytes:
    """Fetch a document over HTTP(S) with an explicit timeout and size bound."""
    if not url.startswith(("https://", "http://")):
        msg = f"URL must be http(s): {url}"
        raise FmindError(msg)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as error:
        msg = f"{url} returned HTTP {error.code}"
        raise FmindError(msg) from error
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        msg = f"could not reach {url}: {error}"
        raise FmindError(msg) from error
    if len(payload) > MAX_BYTES:
        msg = f"{url} returned more than {MAX_BYTES} bytes"
        raise FmindError(msg)
    return payload


def _load(path: Path, url: str, accept: str, parse: Callable[[bytes], T], *, refresh: bool) -> T:
    """Return a parsed document from the cache or the network.

    A fresh cache wins unless `refresh`. When the network fails — or answers with
    something that is not the expected document — a stale cache is still served, so
    the CLI keeps working offline once it has run at least once. Unparseable cached
    bytes are discarded rather than surfaced.
    """
    if not refresh:
        cached = _read_cache(path, CACHE_TTL_SECONDS)
        if cached is not None:
            try:
                return parse(cached)
            except FmindError:
                pass  # a corrupt cache must not break a working command
    try:
        payload = _download(url, accept)
        value = parse(payload)
    except FmindError:
        stale = _read_cache(path, -1)
        if stale is not None:
            try:
                return parse(stale)
            except FmindError:
                pass
        raise
    _write_cache(path, payload)
    return value


def _parse_profile(payload: bytes) -> dict[str, Any]:
    """Decode the portfolio document, rejecting anything that is not one."""
    try:
        document = json.loads(payload)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise FmindError("the profile endpoint did not return JSON") from error
    if not isinstance(document, dict) or "metadata" not in document:
        raise FmindError("the profile endpoint did not return a portfolio document")
    return document


def _parse_markdown(payload: bytes) -> str:
    """Decode an article, rejecting an HTML error page served with a 200."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FmindError("the article was not UTF-8 text") from error
    if not text.strip() or text.lstrip().startswith("<"):
        raise FmindError("the article endpoint did not return Markdown")
    return text


def load_profile(*, refresh: bool = False, url: str = PROFILE_URL) -> dict[str, Any]:
    """Return the portfolio document behind every section command."""
    return _load(cache_path("profile.json"), url, "application/json", _parse_profile, refresh=refresh)


def load_article(slug: str, *, refresh: bool = False, profile_url: str = PROFILE_URL) -> str:
    """Return the Markdown source of one published article."""
    url = article_url(slug, profile_url=profile_url)
    return _load(cache_path("articles", f"{slug}.md"), url, "text/markdown", _parse_markdown, refresh=refresh)
