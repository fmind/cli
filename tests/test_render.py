"""Pure Rich rendering: OSC 8 link guard, empty states, ANSI slots, and console flags."""

import re
from typing import Any

import pytest
from rich.style import Style

from fmind import render
from fmind.api import Profile


def _captured(renderable: Any, *, color: bool = False) -> str:
    out = render.console(color=color)
    with out.capture() as captured:
        out.print(render.Trimmed(renderable), crop=False)
    return captured.get()


@pytest.mark.parametrize("url", ["https://example.test/a", "http://127.0.0.1:8080/x", "mailto:alex@example.test"])
def test_link_attaches_osc8_for_safe_schemes(url: str) -> None:
    text = render._link(url)
    assert isinstance(text.style, Style)
    assert text.style.underline
    assert text.style.link == url


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "relative/path",
        "https://example.test/has space",
        "https://example.test/has\nnewline",
        "https://example.test/has\ttab",
        "https://example.test/\x1b]8;;",
        "https://example.test/\x07bel",
        "https://example.test/\x9cst",
        "https://example.test/\u202ebidi",
        "https://example.test/café",
    ],
)
def test_link_omits_osc8_for_unsafe_or_whitespace_urls(url: str) -> None:
    text = render._link(url)
    assert text.style == "underline"


def test_about_renders_markdown_and_empty_state(document: Profile) -> None:
    document["biography"] = ["A **bold** introduction."]
    rendered = _captured(render.about(document))
    assert "A bold introduction." in rendered
    assert "**" not in rendered

    document["biography"] = []
    assert _captured(render.about(document)) == "no biography published\n"


def test_whoami_and_certifications_handle_empty_optional_lists(document: Profile) -> None:
    document["experience"] = []
    document["services"] = []
    identity = _captured(render.whoami(document))
    assert re.search(r"^Experience +—$", identity, re.MULTILINE)

    document["specializations"] = []
    certs = _captured(render.certifications(document))
    assert "SPECIALIZATIONS" not in certs
    assert "Ground truth" in certs

    document["papers"] = []
    pubs = _captured(render.papers(document))
    assert "PUBLICATIONS" not in pubs
    assert "Ground truth" in pubs


def test_article_body_uses_standard_ansi_slots_for_code() -> None:
    rendered = _captured(render.article_body("```python\ndef greet() -> str:\n    return 'hi'\n```\n"), color=True)
    assert "\x1b[34mdef\x1b[0m" in rendered
    assert "\x1b[94m" not in rendered


@pytest.mark.parametrize("term", ["xterm-256color", "dumb"])
def test_console_respects_no_color_and_explicit_overrides(monkeypatch: pytest.MonkeyPatch, term: str) -> None:
    monkeypatch.setenv("TERM", term)
    monkeypatch.setenv("NO_COLOR", "1")
    assert render.console().no_color
    assert render.console().color_system is None
    assert render.console(color=False).no_color
    assert render.console(color=False).color_system is None
    assert not render.console(color=True).no_color
    assert render.console(color=True).color_system == "truecolor"
    assert render.console(color=True).is_terminal


@pytest.mark.parametrize(
    ("env", "color"),
    [
        ({"FORCE_COLOR": "1", "TERM": "xterm-256color"}, False),
        ({"FORCE_COLOR": "1", "NO_COLOR": "1", "TERM": "xterm-256color"}, None),
    ],
)
def test_no_color_suppresses_sgr_and_osc8_under_force_color(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str], color: bool | None
) -> None:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    out = render.console(color=color)
    assert out.color_system is None
    with out.capture() as captured:
        out.print(render.Trimmed(render._link("https://example.test/docs")), crop=False)
    assert captured.get() == "https://example.test/docs\n"
