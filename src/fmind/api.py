"""Fetch and validate the live documents published by www.fmind.dev."""

from __future__ import annotations

import http.client
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from fmind import __version__

PROFILE_URL = "https://www.fmind.dev/api/profile"
TIMEOUT_SECONDS = 15.0
# Bound memory use even when the origin serves an unexpected document.
MAX_BYTES = 8 * 1024 * 1024
USER_AGENT = f"fmind/{__version__} (+https://github.com/fmind/cli)"
# Slugs reach a URL, so only the shape the site actually mints is accepted.
SLUG_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")
# Keep tabs and line breaks, but never let website text issue terminal commands.
CONTROL_PATTERN = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Only fields consumed by this CLI are required; new website fields pass through.
PROFILE_SHAPE = {
    "metadata": dict.fromkeys(("name", "alternate_name", "job_title", "headline_primary", "email", "site_url"), str),
    "biography": [str],
    "expertise": [{"title": str, "description": str}],
    "experience": [{"company": str, "title": str, "description": str, "tags": [str]}],
    "leadership": [{"organization": str, "role": str, "description": str, "url": str}],
    "certifications": [{"title": str, "issuer": str, "active": bool, "url": str}],
    "specializations": [{"title": str, "issuer_details": str, "url": str}],
    "thesis": {"title": str, "institution_details": str, "description": str, "url": str},
    "papers": [{"title": str, "venue": str, "url": str}],
    "open_source": [{"title": str, "description": str, "href": str}],
    "youtube_series": [{"title": str, "description": str, "url": str}],
    "site_pages": [{"title": str, "description": str, "audience": str, "url": str}],
    "articles": [{"title": str, "description": str, "slug": str, "date": str, "tags": [str], "reading_minutes": int}],
    "services": [{"title": str, "description": str, "badge": str, "cta_url": str}],
}


class FmindError(RuntimeError):
    """A document could not be obtained, or was not the document that was asked for."""


def _http_url(url: str) -> urllib.parse.SplitResult:
    """Reject malformed endpoints before urllib can expose a raw exception."""
    try:
        parts = urllib.parse.urlsplit(url)
        if (
            parts.scheme not in {"http", "https"}
            or not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or any(char.isspace() or ord(char) < 32 for char in url)
        ):
            raise ValueError("invalid endpoint")
        _ = parts.port  # accessing the port validates its syntax and range
    except ValueError as error:
        raise FmindError("FMIND_PROFILE_URL must be a valid http(s) URL without credentials") from error
    return parts


def article_url(slug: str, *, profile_url: str | None = None) -> str:
    """Return the Markdown source URL of an article, on the same origin as the profile."""
    if not SLUG_PATTERN.match(slug):
        msg = f"not an article slug: {slug!r}"
        raise FmindError(msg)
    return origin_url(f"/articles/{slug}.md", profile_url=profile_url)


def origin_url(path: str, *, profile_url: str | None = None) -> str:
    """Resolve a website endpoint on the configured profile origin."""
    parts = _http_url(profile_url if profile_url is not None else os.environ.get("FMIND_PROFILE_URL", PROFILE_URL))
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _download(url: str, accept: str = "application/json") -> bytes:
    """Fetch a document over HTTP(S) with an explicit timeout and size bound."""
    _http_url(url)
    # Ask intermediary HTTP caches to revalidate too; no local copy is kept.
    headers = {"User-Agent": USER_AGENT, "Accept": accept, "Cache-Control": "no-cache"}
    try:
        request = urllib.request.Request(url, headers=headers)  # noqa: S310
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310
            payload = response.read(MAX_BYTES + 1)
            length = response.headers.get("Content-Length")
            if len(payload) <= MAX_BYTES and length is not None and len(payload) != int(length):
                raise http.client.IncompleteRead(payload)
    except urllib.error.HTTPError as error:
        msg = f"the website returned HTTP {error.code}"
        raise FmindError(msg) from error
    except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as error:
        msg = "could not read the website; check your connection and FMIND_PROFILE_URL"
        raise FmindError(msg) from error
    if len(payload) > MAX_BYTES:
        msg = f"the website returned more than {MAX_BYTES} bytes"
        raise FmindError(msg)
    return payload


def _validate(value: object, shape: object, path: str) -> None:
    """Check the few nested JSON shapes needed for rendering, without a dependency."""
    if isinstance(shape, dict) and isinstance(value, dict):
        for key, expected in shape.items():
            _validate(value.get(key), expected, f"{path}.{key}")
    elif isinstance(shape, list) and isinstance(value, list):
        for index, item in enumerate(value):
            _validate(item, shape[0], f"{path}[{index}]")
    elif isinstance(shape, type) and type(value) is shape:
        if isinstance(value, str) and CONTROL_PATTERN.search(value):
            raise FmindError(f"the website returned terminal control characters at {path}")
        return
    else:
        raise FmindError(f"the profile endpoint returned an invalid portfolio document at {path}")


def _parse_profile(payload: bytes) -> dict[str, Any]:
    """Decode the portfolio document, rejecting anything that is not one."""
    try:
        document = json.loads(payload)
    except (ValueError, RecursionError) as error:
        raise FmindError("the profile endpoint did not return JSON") from error
    _validate(document, PROFILE_SHAPE, "profile")
    links = document["thesis"].get("links")
    if links is not None:
        _validate(links, [{"label": str, "url": str}], "profile.thesis.links")
    return document


def _parse_markdown(payload: bytes) -> str:
    """Decode an article, rejecting an HTML error page served with a 200."""
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError as error:
        raise FmindError("the article was not UTF-8 text") from error
    if not text.strip() or text.lstrip().startswith("<"):
        raise FmindError("the article endpoint did not return Markdown")
    if CONTROL_PATTERN.search(text):
        raise FmindError("the article contained terminal control characters")
    return text


def load_profile(*, url: str | None = None) -> dict[str, Any]:
    """Return the portfolio document behind every section command."""
    endpoint = url if url is not None else os.environ.get("FMIND_PROFILE_URL", PROFILE_URL)
    return _parse_profile(_download(endpoint))


def load_article(slug: str, *, profile_url: str | None = None) -> str:
    """Return the Markdown source of one published article."""
    url = article_url(slug, profile_url=profile_url)
    return _parse_markdown(_download(url, "text/markdown"))
