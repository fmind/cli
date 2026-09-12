"""Command surface: every section renders, JSON passthrough, and error handling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from fmind import api
from fmind.cli import app

runner = CliRunner()

SECTIONS = [
    "whoami",
    "about",
    "skills",
    "work",
    "community",
    "cert",
    "papers",
    "project",
    "sites",
    "article",
    "hire",
]


@pytest.fixture(autouse=True)
def _served(cache_home: Path, offline: None) -> None:
    """Every test in this module renders the fixture document."""


@pytest.mark.parametrize("section", SECTIONS)
def test_section_renders(section: str) -> None:
    result = runner.invoke(app, ["--no-color", section])
    assert result.exit_code == 0, result.output
    assert result.output.strip(), f"{section} produced no output"


def test_whoami_shows_identity_and_current_mission() -> None:
    result = runner.invoke(app, ["--no-color", "whoami"])
    assert "Médéric Hurier" in result.output
    assert "AI Security Architect" in result.output
    assert "Decathlon" in result.output, "the current engagement is the mission line"
    assert "Google" not in result.output, "only the current engagement belongs in whoami"


def test_skills_reads_as_a_usage_screen() -> None:
    result = runner.invoke(app, ["--no-color", "skills"])
    assert "USAGE" in result.output
    assert "OPTIONS" in result.output
    assert "--agents" in result.output
    assert "--unlisted" in result.output, "a skill with no mapped flag falls back to its first word"


def test_cert_verify_hides_expired_credentials() -> None:
    full = runner.invoke(app, ["--no-color", "cert"]).output
    assert "ML Engineer" in full
    assert "SPECIALIZATIONS" in full
    verified = runner.invoke(app, ["--no-color", "cert", "--verify"]).output
    assert "Cloud Architect" in verified
    assert "ML Engineer" not in verified
    assert "SPECIALIZATIONS" not in verified


def test_article_is_newest_first_and_respects_limit() -> None:
    result = runner.invoke(app, ["--no-color", "article", "--limit", "1"])
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


def test_search_filters_by_tag() -> None:
    result = runner.invoke(app, ["--no-color", "search", "", "--tag", "LLM"])
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


def test_read_reports_an_unreachable_article(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(url: str, accept: str = "application/json") -> bytes:
        if url.endswith(".md"):
            raise api.FmindError("could not reach the article")
        raise AssertionError("the profile must still come from the cache")

    runner.invoke(app, ["--no-color", "whoami"])  # warm the profile cache
    monkeypatch.setattr("fmind.api._download", fail)
    result = runner.invoke(app, ["read", "newer"])
    assert result.exit_code == 1
    assert "could not reach the article" in result.output


def test_papers_shows_the_thesis_and_publications() -> None:
    output = runner.invoke(app, ["--no-color", "papers"]).output
    assert "Ground truth" in output
    assert "Euphony" in output
    assert "MSR 2017" in output


def test_sites_lists_the_published_tools() -> None:
    output = runner.invoke(app, ["--no-color", "sites"]).output
    assert "Calculator" in output
    assert "leaders" in output


def test_project_respects_top() -> None:
    result = runner.invoke(app, ["--no-color", "project", "--top", "1"])
    assert "repo" in result.output
    assert "series" not in result.output


def test_work_puts_the_current_engagement_first() -> None:
    output = runner.invoke(app, ["--no-color", "work"]).output
    assert output.index("DECATHLON") < output.index("GOOGLE")
    assert "current" in output


def test_hire_marks_the_closed_service() -> None:
    output = runner.invoke(app, ["--no-color", "hire"]).output
    assert "Advisory" in output
    assert "closed" in output
    assert "Mentoring" in output


@pytest.mark.parametrize("section", SECTIONS)
def test_json_output_is_machine_readable(section: str) -> None:
    result = runner.invoke(app, ["--json", section])
    assert result.exit_code == 0, result.output
    json.loads(result.output)  # raises if the section emitted prose


def test_json_read_carries_the_markdown() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "read", "newer"]).output)
    assert payload["slug"] == "newer"
    assert payload["markdown"].startswith("# Newer")


def test_json_search_is_machine_readable() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "search", "older"]).output)
    assert [item["slug"] for item in payload] == ["older"]


def test_json_article_returns_only_the_limit() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "article", "--limit", "1"]).output)
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
        raise api.FmindError("could not reach https://www.fmind.dev/api/profile")

    monkeypatch.setattr("fmind.api._download", fail)
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1
    assert "fmind:" in result.output
    assert "Traceback" not in result.output


def test_refresh_flag_is_passed_through(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    def spy(*, refresh: bool = False) -> dict[str, Any]:
        seen["refresh"] = refresh
        return {
            "metadata": {
                "name": "n",
                "alternate_name": "a",
                "job_title": "j",
                "headline_primary": "h",
                "email": "e",
                "site_url": "s",
            },
            "biography": ["b"],
        }

    monkeypatch.setattr("fmind.cli.load_profile", spy)
    assert runner.invoke(app, ["--refresh", "about"]).exit_code == 0
    assert seen["refresh"] is True
