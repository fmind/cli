"""Command surface: every section renders, JSON passthrough, and error handling."""

import json
import os
import re
import shlex
import signal
import subprocess
import sys
from importlib.metadata import distribution, version
from pathlib import Path
from typing import Any

import pytest
from markdown_it import MarkdownIt
from rich.text import Text
from typer.testing import CliRunner

from fmind import api, cli
from fmind.cli import app

runner = CliRunner()


def test_installed_metadata_declares_the_license() -> None:
    package = distribution("fmind")
    assert package.metadata.get_all("License-File") == ["LICENSE"]


def test_readme_links_and_assets_resolve_for_pypi() -> None:
    root = Path(__file__).parent.parent
    readme = (root / "README.md").read_text(encoding="utf-8")
    tokens = MarkdownIt().parse(readme)
    links = [
        str(child.attrGet("src" if child.type == "image" else "href"))
        for token in tokens
        if token.type == "inline"
        for child in token.children or []
        if child.type in {"link_open", "image"}
    ]
    links += [
        link
        for token in tokens
        if token.type == "html_block"
        for link in re.findall(r'\b(?:href|src)="([^"]+)"', token.content)
    ]
    assert links
    for link in links:
        assert link.startswith("https://"), f"PyPI cannot resolve relative README link {link}"
        bare = link.partition("?")[0].partition("#")[0]
        if match := re.fullmatch(
            r"https://(?:raw\.githubusercontent\.com/fmind/cli/main|github\.com/fmind/cli/blob/main)/(.+)",
            bare,
        ):
            assert (root / match[1]).is_file(), link
        elif match := re.fullmatch(r"https://github\.com/fmind/cli/actions/workflows/([^/]+)(?:/badge\.svg)?", bare):
            assert (root / ".github/workflows" / match[1]).is_file(), link


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
    "tags",
    "news",
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


@pytest.mark.parametrize(
    ("section", "keys", "message"),
    [
        ("about", ["biography"], "no biography published"),
        ("skills", ["expertise"], "no expertise published"),
        ("experiences", ["experience"], "no experience published"),
        ("community", ["leadership"], "no community role published"),
        ("projects", ["open_source", "youtube_series"], "no project published"),
        ("sites", ["site_pages"], "no interactive site published"),
        ("hire", ["services"], "no service published"),
        ("tags", ["tags"], "no tag published"),
    ],
)
def test_empty_sections_say_so(document: dict[str, Any], section: str, keys: list[str], message: str) -> None:
    for key in keys:
        document[key] = []
    result = runner.invoke(app, ["--no-color", section])
    assert result.exit_code == 0, result.output
    assert result.stdout == f"{message}\n"


def test_whoami_shows_identity_and_featured_experience() -> None:
    result = runner.invoke(app, ["--no-color", "whoami"], terminal_width=120)
    assert "Alex Example" in result.output
    assert "Software Architect" in result.output
    assert "Current Company" in result.output, "the first published engagement is featured"
    assert "Past Company" not in result.output, "whoami shows only the first published engagement"


def test_whoami_needs_only_current_website_fields() -> None:
    output = runner.invoke(app, ["--no-color", "whoami"], terminal_width=120).output
    rows = [line.split()[0] for line in output.splitlines() if line.strip()]
    fields = [
        row
        for row in rows
        if row in {"Name", "Role", "Headline", "Experience", "Degree", "Status", "Location", "Contact", "Website"}
    ]
    assert fields == ["Name", "Role", "Headline", "Location", "Experience", "Status", "Contact", "Website"]


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


def test_articles_are_newest_first_and_respect_the_limit(document: dict[str, Any]) -> None:
    document["metadata"]["site_url"] = "https://example.test/"
    result = runner.invoke(app, ["--no-color", "articles", "--limit", "1"])
    assert "Newer" in result.output
    assert "Older" not in result.output
    assert "fmind read newer" in result.output, "a listing must show how to open an entry"
    assert "https://example.test/articles/" in result.output
    assert "//articles/" not in result.output


def test_search_narrows_the_listing() -> None:
    hit = runner.invoke(app, ["--no-color", "search", "older"])
    assert hit.exit_code == 0
    assert "Older" in hit.output
    assert "Newer" not in hit.output


@pytest.mark.parametrize("words", [["older", "llm"], ["older llm"], ["llm", "--tag", "LLM", "older"]])
def test_search_ands_unquoted_words(words: list[str]) -> None:
    hit = runner.invoke(app, ["--no-color", "search", *words])
    assert hit.exit_code == 0, hit.output
    assert "Older" in hit.output
    assert "Newer" not in hit.output


def test_search_narrows_out_disjoint_terms() -> None:
    assert "no article matches" in runner.invoke(app, ["--no-color", "search", "older", "agent"]).output


@pytest.mark.parametrize(
    ("slug", "hint"),
    [
        ("older llm", "search older llm"),
        ("older&", "search 'older&'"),
        ("--draft", "search -- --draft"),
    ],
)
def test_read_miss_hint_runs_as_printed(slug: str, hint: str) -> None:
    result = runner.invoke(app, ["read", "--", slug])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.endswith(f"; try: fmind {hint}\n")
    # A shell would pass these arguments to the suggested command.
    rerun = runner.invoke(app, ["--no-color", *shlex.split(hint)])
    assert rerun.exit_code == 0, rerun.output


def test_search_without_a_match_says_so_and_still_succeeds() -> None:
    result = runner.invoke(app, ["--no-color", "search", "nothing-matches-this"])
    assert result.exit_code == 0
    assert "no article matches" in result.output


@pytest.mark.parametrize("tag", ["LLM", "llm"])
def test_search_filters_by_tag_case_insensitively(tag: str) -> None:
    result = runner.invoke(app, ["--no-color", "search", "--tag", tag])
    assert result.exit_code == 0
    assert "Older" in result.output
    assert "Newer" not in result.output


def test_read_renders_the_published_markdown() -> None:
    result = runner.invoke(app, ["--no-color", "read", "newer"])
    assert result.exit_code == 0, result.output
    assert "The body of the article." in result.output


@pytest.mark.parametrize("slug", ["new", " NEWER "])
def test_read_accepts_partial_and_normalized_slugs(slug: str) -> None:
    assert runner.invoke(app, ["--no-color", "read", slug]).exit_code == 0


@pytest.mark.parametrize("slug", ["", "   "])
def test_read_rejects_empty_slug_before_fetching(monkeypatch: pytest.MonkeyPatch, slug: str) -> None:
    monkeypatch.setattr(api, "_download", lambda *_args: (_ for _ in ()).throw(AssertionError("should not fetch")))
    result = runner.invoke(app, ["read", slug])
    assert result.exit_code == 2
    assert result.stdout == ""
    assert "slug must not be empty" in result.stderr


def test_read_raw_emits_the_markdown_source() -> None:
    result = runner.invoke(app, ["read", "newer", "--raw"])
    assert result.exit_code == 0
    assert result.stdout.startswith("# Newer")


def test_read_reports_an_unknown_slug() -> None:
    result = runner.invoke(app, ["read", "does-not-exist"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "fmind search" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("slug", ["\x1b]52;c;ZXhhbXBsZQ==\x07", "\x9b2J", "\x00", "\ud800"])
def test_unknown_slug_errors_escape_unsafe_characters(slug: str) -> None:
    result = runner.invoke(app, ["read", slug])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert len(result.stderr.splitlines()) == 1
    assert not api.CONTROL_PATTERN.search(result.stderr)
    assert slug.encode("unicode_escape").decode() in result.stderr
    assert "Traceback" not in result.stderr


def test_read_reports_an_ambiguous_slug_on_one_line(document: dict[str, Any]) -> None:
    document["articles"].append(dict(document["articles"][0], slug="newer-still"))
    result = runner.invoke(app, ["read", "new"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "matches 2 articles" in result.stderr
    assert "more)" not in result.stderr
    assert len(result.stderr.splitlines()) == 1

    document["articles"] = [dict(document["articles"][0], slug=f"newer-{i}") for i in range(12)]
    many = runner.invoke(app, ["read", "newer"])
    assert many.exit_code == 1
    assert "matches 12 articles" in many.stderr
    assert "(+2 more)" in many.stderr


def test_read_reports_an_unreachable_article(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> None:
    def fail(url: str, _accept: str = "application/json") -> bytes:
        if url.endswith(".md"):
            raise api.FmindError("could not reach the article")
        return json.dumps(document).encode()

    monkeypatch.setattr("fmind.api._download", fail)
    result = runner.invoke(app, ["read", "newer"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "could not reach the article" in result.stderr


def test_papers_shows_the_thesis_and_publications() -> None:
    output = runner.invoke(app, ["--no-color", "papers"]).output
    assert "Ground truth" in output
    assert "Example Paper" in output
    assert "Example Conference" in output
    assert "  Example Paper  https://example.test/paper-code\n" in output, "each paper links its code"


def test_papers_without_code_show_no_code_row(document: dict[str, Any]) -> None:
    document["thesis"].pop("links", None)
    document["papers"][0].update(code="", code_label="")
    output = runner.invoke(app, ["--no-color", "papers"]).output
    assert "d\nu\n\nPUBLICATIONS\n" in output
    assert "Example Conference\nhttps://orbilu.example/example-paper\n\n" in output


def test_papers_label_unnamed_code(document: dict[str, Any]) -> None:
    document["papers"][0]["code_label"] = ""
    output = runner.invoke(app, ["--no-color", "papers"]).output
    assert "d\nu\n  Code  https://example.test/thesis-code\n\nPUBLICATIONS\n" in output
    assert "  Code  https://example.test/paper-code\n" in output


def test_whoami_shows_location_secondary_headline_and_socials(document: dict[str, Any]) -> None:
    document["metadata"]["socials"].append(
        {"name": "Google Scholar", "url": "https://scholar.example.test/alex", "icon": "scholar"}
    )
    output = runner.invoke(app, ["--no-color", "whoami"], terminal_width=120).output
    assert "Example City" in output
    assert "Example credentials" in output
    assert "Code Host    https://code.example.test/alex\n" in output
    assert "Google Scholar  https://scholar.example.test/alex\n" in output


def test_whoami_skips_an_empty_secondary_headline(document: dict[str, Any]) -> None:
    document["metadata"]["headline_secondary"] = ""
    output = runner.invoke(app, ["--no-color", "whoami"], terminal_width=120).output
    # Rich versions pad the label column differently; no blank line may follow the headline.
    assert re.search(r"^Headline +Example expertise\nLocation ", output, re.MULTILINE)


def test_tags_count_articles_and_show_the_search(document: dict[str, Any]) -> None:
    document["articles"][1]["tags"].append("agent")
    output = runner.invoke(app, ["--no-color", "tags"]).output
    assert "Agent\nd\n2 articles · fmind search --tag Agent\n" in output, "counts match --tag, ignoring case"
    assert "1 article · fmind search --tag LLM\n" in output


def test_news_shows_the_latest_edition_by_default() -> None:
    result = runner.invoke(app, ["--no-color", "news"])
    assert result.exit_code == 0, result.output
    assert result.stdout.startswith("August 16, 2024\nhttps://example.test/news/2024-08-16/\n\nAgents\n")
    assert "Python" in result.stdout
    assert "Summit" not in result.stdout
    assert result.stdout.endswith("1 shown · 3 editions · https://example.test/news/\n")


def test_news_terms_search_further_back_and_keep_matching_links() -> None:
    result = runner.invoke(app, ["--no-color", "news", "agent"])
    assert result.exit_code == 0, result.output
    assert "Agents" in result.stdout
    assert "Keynote" in result.stdout, "a search reads more than today's edition"
    assert "Python" not in result.stdout, "non-matching links are dropped"
    assert "2 shown · 3 editions" in result.stdout


def test_news_limit_bounds_editions() -> None:
    payload = json.loads(runner.invoke(app, ["news", "--limit", "2", "--json"]).stdout)
    assert [edition["slug"] for edition in payload] == ["2024-08-16", "2024-08-15-summit"]
    assert json.loads(runner.invoke(app, ["news", "agent", "--limit", "1", "--json"]).stdout)[0]["slug"] == (
        "2024-08-16"
    )


def test_news_json_keeps_the_published_fields(news_archive: dict[str, Any]) -> None:
    payload = json.loads(runner.invoke(app, ["--json", "news", "2024-07-01"]).stdout)
    assert payload == [news_archive["editions"][2]]


def test_news_without_a_match_says_so_and_still_succeeds() -> None:
    result = runner.invoke(app, ["--no-color", "news", "absent"])
    assert result.exit_code == 0
    assert result.stdout == "no news edition matches\n"


def test_news_failures_are_one_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("fmind.api._download", lambda _url, _accept="": b"[]")
    result = runner.invoke(app, ["news"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "fmind: the news endpoint returned an invalid news archive at news\n"


def test_sites_lists_the_published_tools() -> None:
    output = runner.invoke(app, ["--no-color", "sites"]).output
    assert "Calculator" in output
    assert "leaders" in output


def test_projects_limit_bounds_each_list(document: dict[str, Any]) -> None:
    document["open_source"].append(dict(document["open_source"][0], title="second-repo"))
    result = runner.invoke(app, ["--no-color", "projects", "--limit", "1"])
    assert "repo" in result.output
    assert "second-repo" not in result.output
    assert "VIDEO SERIES" in result.output
    assert "series" in result.output, "video series are never crowded out by repositories"


def test_projects_show_a_distinct_code_repository(document: dict[str, Any]) -> None:
    document["open_source"] = [
        {
            "title": "Example Course",
            "href": "https://course.example.test/",
            "description": "Course site.",
            "repo": "https://code.example.test/course",
        },
        {
            "title": "Same URL",
            "href": "https://code.example.test/same",
            "description": "Repository only.",
            "repo": "https://code.example.test/same",
        },
    ]
    output = runner.invoke(app, ["--no-color", "projects"]).output
    assert "https://course.example.test/\n  Code  https://code.example.test/course\n\n" in output
    assert "  Code  https://code.example.test/same" not in output


def test_projects_json_groups_each_published_list(document: dict[str, Any]) -> None:
    payload = json.loads(runner.invoke(app, ["projects", "--json"]).stdout)
    assert payload == {"open_source": document["open_source"], "youtube_series": document["youtube_series"]}


def test_search_rejects_an_unknown_tag_and_lists_the_published_ones() -> None:
    result = runner.invoke(app, ["search", "--tag", "Agents"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "fmind: unknown tag 'Agents'; choose one of: Agent, LLM\n"


def test_experiences_preserve_website_order_without_inventing_status() -> None:
    output = runner.invoke(app, ["--no-color", "experiences"]).output
    assert output.index("CURRENT COMPANY") < output.index("PAST COMPANY")
    assert " · current" not in output


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


def test_json_escapes_controls_in_unvalidated_fields(document: dict[str, Any]) -> None:
    document["metadata"]["future"] = "x\x9b2J\x7f"
    result = runner.invoke(app, ["whoami", "--json"])
    assert result.exit_code == 0, result.output
    assert not api.CONTROL_PATTERN.search(result.stdout)
    assert json.loads(result.stdout)["metadata"]["future"] == "x\x9b2J\x7f"


@pytest.mark.parametrize("args", [["--json", "read", "newer"], ["--json", "read", "newer", "--raw"]])
def test_json_read_carries_the_markdown_and_beats_raw(document: dict[str, Any], args: list[str]) -> None:
    # An index field named like the body must not replace the fetched Markdown.
    document["articles"][0]["markdown"] = "https://example.test/articles/newer.md"
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    assert result.stderr == ""
    payload = json.loads(result.stdout)
    assert payload["slug"] == "newer"
    assert payload["markdown"].startswith("# Newer")
    assert payload["title"] == "Newer"


def test_json_search_is_machine_readable() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "search", "older"]).output)
    assert [item["slug"] for item in payload] == ["older"]


def test_json_articles_return_only_the_limit() -> None:
    payload = json.loads(runner.invoke(app, ["--json", "articles", "--limit", "1"]).output)
    assert [item["title"] for item in payload] == ["Newer"]


def test_version_exits_before_any_fetch() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.stdout == f"fmind {version('fmind')}\n"
    assert not result.stderr


def test_module_entrypoint_runs_the_cli(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    import runpy

    monkeypatch.setattr(sys, "argv", ["fmind", "--version"])
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_module("fmind", run_name="__main__")
    assert exit_info.value.code == 0
    assert capsys.readouterr().out == f"fmind {version('fmind')}\n"


def test_entrypoint_exits_cleanly_on_usage_interrupt_and_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as failed:
        app(["read", "does-not-exist"], standalone_mode=True)
    assert failed.value.code == 1
    assert "fmind: no article matches" in capsys.readouterr().err

    with pytest.raises(SystemExit) as usage:
        app(["--no-such-option"], standalone_mode=True)
    assert usage.value.code == 2
    assert capsys.readouterr().err

    monkeypatch.setattr(cli, "load_profile", lambda: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(SystemExit) as interrupted:
        app(["whoami"], standalone_mode=True)
    assert interrupted.value.code == 130
    assert capsys.readouterr() == ("", "")


def test_no_arguments_shows_the_whoami_card_and_points_to_help() -> None:
    result = runner.invoke(app, ["--no-color"])
    assert result.exit_code == 0, result.output
    assert "Alex Example" in result.stdout
    assert result.stdout.rstrip().endswith("fmind --help lists every command.")


def test_no_arguments_with_json_prints_only_the_whoami_data(document: dict[str, Any]) -> None:
    result = runner.invoke(app, ["--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["metadata"] == document["metadata"]


def test_unreachable_profile_reports_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(_url: str, _accept: str = "application/json") -> bytes:
        raise api.FmindError("could not reach https://example.test/api/profile")

    monkeypatch.setattr("fmind.api._download", fail)
    result = runner.invoke(app, ["whoami"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert "fmind:" in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("flag", ["-h", "--help"])
@pytest.mark.parametrize("command", [[], ["experiences"], ["read"]])
def test_help_exposes_json_and_omits_refresh(flag: str, command: list[str]) -> None:
    result = runner.invoke(app, [*command, flag])
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
    monkeypatch.setattr("fmind.api._download", lambda *_args: b'{"metadata": {}}')
    result = runner.invoke(app, command)
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("fmind: ")
    assert len(result.stderr.splitlines()) == 1
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "command",
    [["projects", "--limit", "0"], ["articles", "--limit", "201"], ["search", "--limit", "0"]],
)
def test_invalid_usage_exits_without_data(command: list[str]) -> None:
    result = runner.invoke(app, command)
    assert result.exit_code == 2
    assert result.stdout == ""


def test_colour_flags_control_ansi_and_never_pollute_json() -> None:
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


@pytest.mark.parametrize("position", ["before", "after"])
def test_summary_json_includes_the_information_shown_in_text(document: dict[str, Any], position: str) -> None:
    def payload(command: str) -> Any:
        args = ["--json", command] if position == "before" else [command, "--json"]
        result = runner.invoke(app, args)
        assert result.exit_code == 0, result.output
        assert not result.stderr
        return json.loads(result.stdout)

    identity = payload("whoami")
    assert identity["metadata"] == document["metadata"]
    assert identity["experience"] == [document["experience"][0]]
    assert identity["services"] == document["services"]
    credentials = payload("certifications")
    assert credentials["certifications"] == document["certifications"]
    assert credentials["thesis"] == document["thesis"]
    assert credentials["specializations"] == document["specializations"]
    publications = payload("papers")
    assert publications == {"thesis": document["thesis"], "papers": document["papers"]}

    document["experience"] = []
    document["certifications"] = []
    document["specializations"] = []
    assert payload("whoami")["experience"] == []
    credentials = payload("certifications")
    assert credentials["certifications"] == []
    assert credentials["specializations"] == []
    assert credentials["thesis"] == document["thesis"]


def test_identity_and_community_remain_readable_at_40_columns(
    monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]
) -> None:
    monkeypatch.setenv("COLUMNS", "40")
    identity = runner.invoke(app, ["--no-color", "whoami"])
    assert identity.exit_code == 0, identity.output
    assert document["metadata"]["name"] in identity.stdout
    assert document["metadata"]["job_title"] in identity.stdout
    assert document["metadata"]["headline_primary"] in identity.stdout
    assert identity.stdout.count(document["metadata"]["name"]) == 1

    document["leadership"][0]["organization"] = "Example Research Foundation"
    document["leadership"][0]["description"] = "Supporting the research community."
    community = runner.invoke(app, ["--no-color", "community"])
    assert community.exit_code == 0, community.output
    assert document["leadership"][0]["organization"] in community.stdout
    assert document["leadership"][0]["description"] in community.stdout
    for output in (identity.stdout, community.stdout):
        # Links are never folded, so only a line ending in one may run past the width.
        assert all(len(line) <= 40 or line.split()[-1].startswith("https://") for line in output.splitlines())
        assert "\x1b" not in output


@pytest.mark.parametrize(
    ("command", "section"),
    [("community", "leadership"), ("certifications", "certifications"), ("certifications", "specializations")],
)
def test_published_links_are_visible(document: dict[str, Any], command: str, section: str) -> None:
    url = f"https://example.test/{section}"
    document[section][0]["url"] = url
    result = runner.invoke(app, ["--no-color", command])
    assert result.exit_code == 0, result.output
    assert url in result.stdout


@pytest.mark.parametrize("section", [*SECTIONS, "read newer"])
@pytest.mark.parametrize("colour", ["--no-color", "--color", "FORCE_COLOR"])
def test_redirected_output_has_no_trailing_whitespace(section: str, colour: str) -> None:
    # Forced colour makes Rich treat the redirected stream as a terminal.
    flags, env = ([], {"FORCE_COLOR": "1", "TERM": "xterm-256color"}) if colour == "FORCE_COLOR" else ([colour], {})
    result = runner.invoke(app, [*flags, *section.split()], terminal_width=120, env=env)
    assert result.exit_code == 0, result.output
    if colour in {"--color", "FORCE_COLOR"} and section != "about":
        assert "\x1b[" in result.stdout
    for line in result.stdout.splitlines():
        assert not line.endswith(" ")
        assert Text.from_ansi(line).plain == Text.from_ansi(line).plain.rstrip()


def test_long_links_stay_on_one_line(document: dict[str, Any]) -> None:
    url = "https://example.test/" + "a" * 150
    document["services"][1]["cta_url"] = url
    result = runner.invoke(app, ["--no-color", "hire"], terminal_width=40)
    assert result.exit_code == 0, result.output
    assert url in result.stdout.splitlines()


@pytest.mark.parametrize("command", [[], ["whoami"]])
@pytest.mark.parametrize("color", ["--color", "--no-color"])
def test_card_links_are_not_cropped(
    document: dict[str, Any], command: list[str], color: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "40")
    document["metadata"]["email"] = "contact@" + "a" * 90 + ".test"
    document["metadata"]["site_url"] = "https://example.test/" + "a" * 100
    result = runner.invoke(app, [color, *command], terminal_width=40)
    assert result.exit_code == 0, result.output
    visible = Text.from_ansi(result.stdout).plain
    for field in ("email", "site_url"):
        assert any(document["metadata"][field] in line for line in visible.splitlines())


class _ClosedPipe:
    """A stdout whose reader has gone away, like `fmind ... | head -0`."""

    encoding = "utf-8"

    def write(self, text: str) -> int:
        return len(text)

    def flush(self) -> None:
        raise BrokenPipeError(32, "Broken pipe")

    def isatty(self) -> bool:
        return False


@pytest.mark.parametrize(
    "command",
    [["--no-color", "articles"], ["--color", "articles"], ["--json", "articles"], ["read", "newer", "--raw"]],
)
def test_closed_reader_ends_quietly(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], command: list[str]
) -> None:
    monkeypatch.setattr(sys, "stdout", _ClosedPipe())
    with pytest.raises(SystemExit) as exit_info:
        app(command, standalone_mode=True)
    # Closed downstream pipes exit 1 quietly; stdout flushed inside the command.
    assert exit_info.value.code == 1
    assert capsys.readouterr().err == ""


def test_pager_is_used_only_for_an_interactive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    class Terminal:
        def isatty(self) -> bool:
            return True

        def fileno(self) -> int:
            return 1  # setupterm reads the terminfo entry; the descriptor need not be a terminal

    monkeypatch.setattr(sys, "stdin", Terminal())
    monkeypatch.setattr(sys, "stdout", Terminal())
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setenv("PAGER", "less -S")
    assert cli._pager_command() == ["less", "-S"]
    for disabled in ("", "cat", "/bin/cat", "'unbalanced"):
        monkeypatch.setenv("PAGER", disabled)
        assert cli._pager_command() is None
    monkeypatch.delenv("PAGER")
    assert cli._pager_command() == ["less"]
    for term in ("dumb", ""):
        monkeypatch.setenv("TERM", term)
        assert cli._pager_command() is None
    monkeypatch.delenv("TERM")
    assert cli._pager_command() is None, "less would wait at a hidden prompt without TERM"
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert cli._pager_command() is None


def test_pager_needs_a_terminal_it_can_drive(monkeypatch: pytest.MonkeyPatch) -> None:
    import curses

    def unknown(*_args: object) -> None:
        raise curses.error("setupterm: could not find terminal")

    monkeypatch.setenv("TERM", "xterm-nosuchterm")
    monkeypatch.setattr(curses, "setupterm", unknown)
    assert not cli._full_screen_terminal()
    monkeypatch.setitem(sys.modules, "curses", None)
    assert cli._full_screen_terminal(), "without curses (Windows), TERM is trusted"


@pytest.mark.parametrize(
    ("term", "expected"), [("xterm-256color", True), ("xterm-nosuchterm", False), ("unknown", False)]
)
def test_pager_checks_the_terminfo_database(term: str, expected: bool) -> None:
    # A fresh interpreter: curses keeps the first terminal it sets up for the whole process.
    # `unknown` is in terminfo, but generic; less would wait at a hidden prompt for it too.
    script = "from fmind import cli; print(cli._full_screen_terminal())"
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        env={**os.environ, "TERM": term},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
        check=True,
    )
    assert result.stdout == f"{expected}\n"


class _Pager:
    """A pager process: records its input and exits with `code`, or is interrupted first."""

    def __init__(
        self,
        command: list[str],
        *,
        code: int = 0,
        interrupt: bool = False,
        interrupt_close: bool = False,
        quit_early: bool = False,
        has_stdin: bool = True,
        **kwargs: Any,
    ) -> None:
        self.command = command
        self.kwargs = kwargs
        self.code = code
        self.interrupt = interrupt
        self.interrupt_close = interrupt_close
        self.quit_early = quit_early
        self.written = b""
        self.waits = 0
        self.stdin = self if has_stdin else None

    def __enter__(self) -> _Pager:
        return self

    def __exit__(self, *_args: object) -> None:
        if self.interrupt_close:
            raise KeyboardInterrupt

    def write(self, data: bytes) -> int:
        if self.interrupt:
            # Ctrl-C while blocked on a full pipe, as when less waits at its prompt.
            raise KeyboardInterrupt
        if self.quit_early:
            raise BrokenPipeError(32, "Broken pipe")
        self.written += data
        return len(data)

    def wait(self) -> int:
        self.waits += 1
        if self.interrupt and self.waits == 1:
            raise KeyboardInterrupt
        return self.code

    def kill(self) -> None:
        raise AssertionError("a killed pager leaves the terminal in raw mode")


def test_system_pager_keeps_colour_and_respects_less(monkeypatch: pytest.MonkeyPatch) -> None:
    pagers: list[_Pager] = []

    def popen(command: list[str], **kwargs: Any) -> _Pager:
        pagers.append(_Pager(command, **kwargs))
        return pagers[-1]

    monkeypatch.setattr("subprocess.Popen", popen)
    monkeypatch.delenv("LESS", raising=False)
    cli._SystemPager(["less"]).show("text")
    monkeypatch.setenv("LESS", "-S")
    cli._SystemPager(["less"]).show("more")
    assert [pager.kwargs["env"]["LESS"] for pager in pagers] == ["FRX", "-S"]
    assert pagers[0].command == ["less"]
    assert pagers[0].written == b"text"
    assert pagers[0].kwargs["stdin"] == subprocess.PIPE
    assert pagers[0].kwargs["stderr"] == subprocess.DEVNULL


@pytest.mark.parametrize("ending", ["interrupt", "interrupt_close", "quit_early", "no_stdin"])
def test_pager_owns_the_terminal_until_it_quits(monkeypatch: pytest.MonkeyPatch, ending: str) -> None:
    kwargs = {"has_stdin": False} if ending == "no_stdin" else {ending: True}
    pager = _Pager(["less"], **kwargs)
    monkeypatch.setattr("subprocess.Popen", lambda _command, **_kwargs: pager)
    cli._SystemPager(["less"]).show("text")
    # After Ctrl-C (during write or close) or early quit, wait for the pager to restore the terminal.
    assert pager.waits == (2 if ending == "interrupt" else 1)


@pytest.mark.parametrize("code", [-signal.SIGINT, 128 + signal.SIGINT])
def test_pager_sigint_exit_propagates_interrupt(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    pager = _Pager(["more"], code=code)
    monkeypatch.setattr("subprocess.Popen", lambda _command, **_kwargs: pager)
    with pytest.raises(KeyboardInterrupt):
        cli._SystemPager(["more"]).show("text")


@pytest.mark.parametrize("failure", ["launch", "exit"])
def test_pager_failures_are_safe_errors(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    error = OSError("private launch diagnostic")

    def popen(command: list[str], **kwargs: Any) -> _Pager:
        if failure == "launch":
            raise error
        return _Pager(command, code=1, **kwargs)

    monkeypatch.setattr(cli, "_pager_command", lambda: ["pager"])
    monkeypatch.setattr("subprocess.Popen", popen)
    result = runner.invoke(app, ["--color", "read", "newer"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "fmind: could not display the article with PAGER; check PAGER or use PAGER=cat\n"
    with pytest.raises(api.FmindError) as caught:
        cli._SystemPager(["pager"]).show("text")
    if failure == "launch":
        assert caught.value.__cause__ is error


def test_only_read_pages_on_an_interactive_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    shown: list[str] = []
    monkeypatch.setattr(cli, "_pager_command", lambda: ["less"])
    monkeypatch.setattr(cli._SystemPager, "show", lambda _self, content: shown.append(content))
    whoami_result = runner.invoke(app, ["--color", "whoami"])
    assert whoami_result.exit_code == 0, whoami_result.output
    assert shown == [], "non-read commands never invoke the pager"

    read_result = runner.invoke(app, ["--color", "read", "newer"])
    assert read_result.exit_code == 0, read_result.output
    assert len(shown) == 1
    assert "The body of the article." in shown[0]
    assert "The body of the article." not in read_result.stdout
