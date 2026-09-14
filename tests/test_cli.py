"""Command surface: every section renders, JSON passthrough, and error handling."""

from __future__ import annotations

import json
from typing import Any

import pytest
from rich.text import Text
from typer.testing import CliRunner

from fmind import api
from fmind.cli import app

runner = CliRunner()

SECTIONS = [
    "whoami",
    "about",
    "skills",
    "experiences",
    "certifications",
    "community",
    "papers",
    "projects",
    "sites",
    "articles",
    "hire",
]


@pytest.fixture(autouse=True)
def _served(offline: None) -> None:
    """Every test in this module renders the fixture document."""


@pytest.mark.parametrize("section", SECTIONS)
def test_section_renders(section: str) -> None:
    result = runner.invoke(app, ["--no-color", section])
    assert result.exit_code == 0, result.output
    assert result.output.strip(), f"{section} produced no output"


def test_whoami_shows_identity_and_current_mission() -> None:
    result = runner.invoke(app, ["--no-color", "whoami"], terminal_width=120)
    assert "Alex Example" in result.output
    assert "Software Architect" in result.output
    assert "Current Company" in result.output, "the current engagement is the mission line"
    assert "Past Company" not in result.output, "only the current engagement belongs in whoami"


def test_whoami_needs_only_current_website_fields() -> None:
    output = runner.invoke(app, ["--no-color", "whoami"], terminal_width=120).output
    rows = [line.split()[0] for line in output.splitlines() if line.strip()]
    fields = [
        row for row in rows if row in {"Name", "Role", "Mission", "Degree", "Status", "Location", "Contact", "Website"}
    ]
    assert fields == ["Name", "Role", "Mission", "Status", "Contact", "Website"]


def test_skills_renders_the_published_titles(document: dict[str, Any]) -> None:
    result = runner.invoke(app, ["--no-color", "skills"])
    assert result.exit_code == 0
    for card in document["expertise"]:
        assert card["title"] in result.stdout
        assert card["description"] in result.stdout
    assert "USAGE" not in result.stdout


def test_certifications_spell_their_state_the_way_the_website_does() -> None:
    output = runner.invoke(app, ["--no-color", "certifications"]).output
    assert "[active] " in output
    assert "[past] " in output
    assert "Cloud Architect" in output
    assert "ML Engineer" in output
    assert "SPECIALIZATIONS" in output
    # One listing, narrowed with jq rather than with a flag of its own.
    assert runner.invoke(app, ["certifications", "--verify"]).exit_code == 2


def test_articles_are_newest_first_and_respect_the_limit() -> None:
    result = runner.invoke(app, ["--no-color", "articles", "--limit", "1"])
    assert "Newer" in result.output
    assert "Older" not in result.output
    assert "fmind read newer" in result.output, "a listing must show how to open an entry"


def test_search_narrows_the_listing() -> None:
    hit = runner.invoke(app, ["--no-color", "search", "older"])
    assert hit.exit_code == 0
    assert "Older" in hit.output
    assert "Newer" not in hit.output


def test_search_without_a_match_says_so_and_still_succeeds() -> None:
    result = runner.invoke(app, ["--no-color", "search", "nothing-matches-this"])
    assert result.exit_code == 0
    assert "no article matches" in result.output


def test_search_filters_by_tag_without_a_query() -> None:
    result = runner.invoke(app, ["--no-color", "search", "--tag", "LLM"])
    assert "Older" in result.output
    assert "Newer" not in result.output


def test_read_renders_the_published_markdown() -> None:
    result = runner.invoke(app, ["--no-color", "read", "newer"])
    assert result.exit_code == 0, result.output
    assert "The body of the article." in result.output


def test_read_accepts_a_partial_slug() -> None:
    assert runner.invoke(app, ["--no-color", "read", "new"]).exit_code == 0


def test_read_raw_emits_the_markdown_source() -> None:
    result = runner.invoke(app, ["read", "newer", "--raw"])
    assert result.exit_code == 0
    assert result.output.startswith("# Newer")


def test_read_reports_an_unknown_slug() -> None:
    result = runner.invoke(app, ["read", "does-not-exist"])
    assert result.exit_code == 1
    assert "fmind search" in result.output
    assert "Traceback" not in result.output


def test_read_reports_an_ambiguous_slug(document: dict[str, Any]) -> None:
    document["articles"].append(dict(document["articles"][0], slug="newer-still"))
    result = runner.invoke(app, ["read", "new"])
    assert result.exit_code == 1
    assert "matches 2 articles" in result.output


def test_read_reports_an_unreachable_article(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> None:
    def fail(url: str, accept: str = "application/json") -> bytes:
        if url.endswith(".md"):
            raise api.FmindError("could not reach the article")
        return json.dumps(document).encode()

    monkeypatch.setattr("fmind.api._download", fail)
    result = runner.invoke(app, ["read", "newer"])
    assert result.exit_code == 1
    assert "could not reach the article" in result.output


def test_papers_shows_the_thesis_and_publications() -> None:
    output = runner.invoke(app, ["--no-color", "papers"]).output
    assert "Ground truth" in output
    assert "Example Paper" in output
    assert "Example Conference" in output


def test_sites_lists_the_published_tools() -> None:
    output = runner.invoke(app, ["--no-color", "sites"]).output
    assert "Calculator" in output
    assert "leaders" in output


def test_projects_respect_the_limit() -> None:
    result = runner.invoke(app, ["--no-color", "projects", "--limit", "1"])
    assert "repo" in result.output
    assert "series" not in result.output


def test_experiences_put_the_current_engagement_first() -> None:
    output = runner.invoke(app, ["--no-color", "experiences"]).output
    assert output.index("CURRENT COMPANY") < output.index("PAST COMPANY")
    assert "current" in output


def test_hire_marks_the_closed_service() -> None:
    output = runner.invoke(app, ["--no-color", "hire"]).output
    assert "Advisory" in output
    assert "closed" in output
    assert "Mentoring" in output


@pytest.mark.parametrize("section", SECTIONS)
@pytest.mark.parametrize("position", ["before", "after"])
def test_json_output_is_machine_readable(section: str, position: str) -> None:
    args = ["--json", section] if position == "before" else [section, "--json"]
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    json.loads(result.stdout)  # raises if the section emitted prose
    assert result.stderr == ""


def test_json_read_carries_the_markdown() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "read", "newer"]).output)
    assert payload["slug"] == "newer"
    assert payload["markdown"].startswith("# Newer")


def test_json_search_is_machine_readable() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "search", "older"]).output)
    assert [item["slug"] for item in payload] == ["older"]


def test_json_articles_return_only_the_limit() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "articles", "--limit", "1"]).output)
    assert [item["title"] for item in payload] == ["Newer"]


def test_version_exits_before_any_fetch() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "fmind 0." in result.output


def test_no_arguments_shows_help() -> None:
    result = runner.invoke(app, [])
    assert "Commands" in result.output


def test_unreachable_profile_reports_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(url: str, accept: str = "application/json") -> bytes:
        raise api.FmindError("could not reach https://example.test/api/profile")

    monkeypatch.setattr("fmind.api._download", fail)
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1
    assert "fmind:" in result.output
    assert "Traceback" not in result.output


@pytest.mark.parametrize("command", [[], ["experiences"], ["read"]])
def test_help_exposes_json_and_omits_refresh(command: list[str]) -> None:
    result = runner.invoke(app, [*command, "--help"])
    assert result.exit_code == 0
    # CI forces Rich colour, which can insert ANSI sequences inside option names.
    visible = Text.from_ansi(result.stdout).plain
    assert "--json" in visible
    assert "--refresh" not in visible


def test_json_experiences_are_the_website_section(document: dict[str, Any]) -> None:
    result = runner.invoke(app, ["experiences", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout) == document["experience"]


@pytest.mark.parametrize("command", [["search", "older"], ["read", "newer"], ["read", "newer", "--raw"]])
def test_article_commands_accept_trailing_json(command: list[str]) -> None:
    result = runner.invoke(app, [*command, "--json"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)
    assert result.stderr == ""


def test_json_option_does_not_leak_between_invocations() -> None:
    assert runner.invoke(app, ["experiences", "--json"]).exit_code == 0
    plain = runner.invoke(app, ["experiences"])
    assert plain.exit_code == 0
    assert not plain.stdout.startswith("[")


@pytest.mark.parametrize("command", [["experiences"], ["experiences", "--json"]])
def test_malformed_profile_is_a_one_line_error(monkeypatch: pytest.MonkeyPatch, command: list[str]) -> None:
    monkeypatch.setattr("fmind.api._download", lambda *args: b'{"metadata": {}}')
    result = runner.invoke(app, command)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("fmind: ")
    assert len(result.stderr.splitlines()) == 1
    assert "Traceback" not in result.stderr


def test_ambiguous_slug_error_is_one_line(document: dict[str, Any]) -> None:
    document["articles"].append(dict(document["articles"][0], slug="newer-still"))
    result = runner.invoke(app, ["read", "new"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1


def test_plain_biography_renders_markdown(document: dict[str, Any]) -> None:
    document["biography"] = ["A **bold** introduction."]
    result = runner.invoke(app, ["--no-color", "about"])
    assert result.exit_code == 0
    assert "A bold introduction." in result.stdout
    assert "**" not in result.stdout


def test_community_keeps_the_full_organization(document: dict[str, Any]) -> None:
    document["leadership"][0]["organization"] = "Example Research Foundation"
    result = runner.invoke(app, ["--no-color", "community"], terminal_width=120)
    assert result.exit_code == 0
    assert "Example Research Foundation" in result.stdout


@pytest.mark.parametrize(
    "command",
    [["projects", "--limit", "0"], ["articles", "--limit", "201"], ["search", "--limit", "0"]],
)
def test_invalid_usage_exits_without_data(command: list[str]) -> None:
    result = runner.invoke(app, command)
    assert result.exit_code == 2
    assert result.stdout == ""


@pytest.mark.parametrize("term", ["xterm-256color", "dumb"])
def test_colour_respects_no_color_and_explicit_flags(monkeypatch: pytest.MonkeyPatch, term: str) -> None:
    from fmind import render

    monkeypatch.setenv("TERM", term)
    monkeypatch.setenv("NO_COLOR", "1")
    assert render.console().no_color
    assert render.console(color=False).no_color
    assert not render.console(color=True).no_color
    assert render.console(color=True).is_terminal
    result = runner.invoke(app, ["--no-color", "experiences"])
    assert "\x1b[" not in result.stdout
    coloured = runner.invoke(app, ["--color", "experiences"])
    assert "\x1b[" in coloured.stdout
    json_result = runner.invoke(app, ["--color", "experiences", "--json"])
    assert "\x1b[" not in json_result.stdout
    assert json.loads(json_result.stdout)


def test_remote_organization_is_literal_text(document: dict[str, Any]) -> None:
    document["leadership"][0]["organization"] = "[bold]Example[/broken]"
    result = runner.invoke(app, ["--no-color", "community"], terminal_width=120)
    assert result.exit_code == 0, result.output
    assert "[bold]Example[/broken]" in result.stdout
