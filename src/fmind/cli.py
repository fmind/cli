"""Command surface, mirroring the sections of www.fmind.dev."""

from __future__ import annotations

import asyncio
import json
import os
import shlex
import shutil
import subprocess
import sys
from typing import Annotated, Any

import typer
from rich.console import Console, RenderableType
from rich.pager import Pager

from fmind import __version__, articles, render
from fmind.api import FmindError, load_article, load_profile

app = typer.Typer(
    name="fmind",
    help="Read Médéric Hurier's (Fmind) portfolio from the terminal. Every command renders the live "
    "profile published at https://www.fmind.dev/api/profile. Without a command, show the whoami card. "
    "Use mcp for the stdio MCP bridge.",
    add_completion=False,
    rich_markup_mode="rich",
    pretty_exceptions_enable=False,
)

JsonOption = Annotated[bool, typer.Option("--json", help="Print the command's data as JSON instead of prose.")]
# One option name for "how many", on every command that prints a list.
LimitOption = Annotated[int, typer.Option("--limit", min=1, max=200, help="How many entries to show.")]


def _version(value: bool) -> None:
    if value:
        typer.echo(f"fmind {__version__}")
        raise typer.Exit


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    as_json: JsonOption = False,
    color: Annotated[
        bool | None, typer.Option("--color/--no-color", help="Force or suppress ANSI colour; auto by default.")
    ] = None,
    _v: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True, help="Show the version.")] = False,
) -> None:
    """Set output options before the command, or use --json on any command."""
    if ctx.invoked_subcommand is None:
        # A bare `fmind` works like a business card; `--help` lists everything else.
        whoami(ctx)
        if not as_json:
            _console(ctx).print("\nfmind --help lists every command.", style="dim")


def _fail(message: str) -> typer.Exit:
    """Report a clear one-line error on stderr and end the command."""
    typer.echo(f"fmind: {' '.join(message.split())}", err=True)
    return typer.Exit(code=1)


def _doc() -> dict[str, Any]:
    """Load the profile, reporting a clear error instead of a traceback."""
    try:
        return load_profile()
    except FmindError as error:
        raise _fail(str(error)) from error


class _SystemPager(Pager):
    """Page through the user's pager with colour, quitting at once when the text fits one screen."""

    def __init__(self, command: list[str]) -> None:
        self.command = command

    def show(self, content: str) -> None:
        # Like Git: respect an explicit LESS, otherwise keep colours (-R), skip
        # paging for short output (-F), and leave the text on screen (-X).
        environment = {**os.environ, "LESS": os.environ.get("LESS", "FRX")}
        subprocess.run(self.command, input=content.encode(), env=environment, check=False)  # noqa: S603


def _pager_command() -> list[str] | None:
    """Return the pager for an interactive terminal, or None to print directly."""
    if not (sys.stdin.isatty() and sys.stdout.isatty()) or os.environ.get("TERM") == "dumb":
        return None
    try:
        command = shlex.split(os.environ.get("PAGER", "less"))
    except ValueError:
        return None
    if not command or command[0] == "cat" or shutil.which(command[0]) is None:
        return None
    return command


def _console(ctx: typer.Context) -> Console:
    return render.console(color=ctx.find_root().params["color"])


def _write(text: str) -> None:
    """Write and flush, so a closed reader (`| head`) fails inside Click's EPIPE handling, not at exit."""
    sys.stdout.write(text)
    sys.stdout.flush()


def _emit(ctx: typer.Context, body: RenderableType, payload: Any, *, as_json: bool, page: bool = False) -> None:
    """Print either the rendered section or its JSON data."""
    if as_json or ctx.find_root().params["as_json"]:
        _write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        return
    out = _console(ctx)
    if not out.is_terminal:
        out.print(render.Trimmed(body), crop=False)
        return
    command = _pager_command() if page else None
    if command is None:
        out.print(body, crop=False)
        return
    with out.pager(pager=_SystemPager(command), styles=True):
        out.print(body, crop=False)


@app.command()
def whoami(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """Name, featured experience, availability, and contact."""
    doc = _doc()
    _emit(
        ctx,
        render.whoami(doc),
        {"metadata": doc["metadata"], "experience": doc["experience"][:1], "services": doc["services"]},
        as_json=as_json,
    )


@app.command()
def about(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """The biography, as published on the site."""
    doc = _doc()
    _emit(ctx, render.about(doc), doc["biography"], as_json=as_json)


@app.command()
def skills(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """Core expertise, as published on the site."""
    doc = _doc()
    _emit(ctx, render.skills(doc), doc["expertise"], as_json=as_json)


@app.command()
def experiences(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """Engagements in the order published by the website."""
    doc = _doc()
    _emit(ctx, render.experiences(doc), doc["experience"], as_json=as_json)


@app.command()
def certifications(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """Certifications, the PhD, and specializations."""
    doc = _doc()
    # Every credential is listed with its state spelled out, the way the website
    # spells it; `--json` and jq narrow the list better than a flag could.
    _emit(
        ctx,
        render.certifications(doc),
        {"certifications": doc["certifications"], "thesis": doc["thesis"], "specializations": doc["specializations"]},
        as_json=as_json,
    )


@app.command()
def community(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """Ambassador and advisory roles."""
    doc = _doc()
    _emit(ctx, render.community(doc), doc["leadership"], as_json=as_json)


@app.command()
def papers(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """The doctorate and the peer-reviewed publications."""
    doc = _doc()
    _emit(ctx, render.papers(doc), {"thesis": doc["thesis"], "papers": doc["papers"]}, as_json=as_json)


@app.command()
def projects(ctx: typer.Context, limit: LimitOption = 6, as_json: JsonOption = False) -> None:
    """Open-source repositories and video series; --limit bounds each list."""
    doc = _doc()
    payload = {"open_source": doc["open_source"][:limit], "youtube_series": doc["youtube_series"][:limit]}
    _emit(ctx, render.projects(doc, limit=limit), payload, as_json=as_json)


@app.command()
def sites(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """Interactive tools published alongside the writing."""
    doc = _doc()
    _emit(ctx, render.sites(doc), doc["site_pages"], as_json=as_json)


# Named for the command it is, not for the function: `articles` is the selection
# module this body reads.
@app.command("articles")
def list_articles(ctx: typer.Context, limit: LimitOption = 6, as_json: JsonOption = False) -> None:
    """The most recent writing."""
    doc = _doc()
    posts = articles.latest(doc["articles"], limit=limit)
    footer = f"{len(doc['articles'])} published · {doc['metadata']['site_url']}/articles/"
    _emit(ctx, render.articles(posts, footer=footer), posts, as_json=as_json)


@app.command()
def search(
    ctx: typer.Context,
    # Optional, so filtering by tag alone needs no empty positional argument.
    query: Annotated[str, typer.Argument(help="Terms to match against titles, summaries, tags and slugs.")] = "",
    tag: Annotated[str | None, typer.Option("--tag", help="Restrict to one of the site's tags, such as Agent.")] = None,
    limit: LimitOption = 10,
    as_json: JsonOption = False,
) -> None:
    """Find articles by term, newest match first."""
    doc = _doc()
    if tag is not None:
        names = [entry["name"] for entry in doc["tags"]]
        if tag.lower() not in {name.lower() for name in names}:
            raise _fail(f"unknown tag {tag!r}; choose one of: {', '.join(names)}")
    found = articles.search(doc["articles"], query, tag=tag, limit=limit)
    footer = f"{len(found)} shown · {len(doc['articles'])} published · fmind read <slug> opens one"
    _emit(ctx, render.articles(found, footer=footer), found, as_json=as_json)


@app.command()
def read(
    ctx: typer.Context,
    slug: Annotated[str, typer.Argument(help="Article slug, or enough of it to be unambiguous.")],
    raw: Annotated[bool, typer.Option("--raw", help="Print the Markdown source instead of rendering it.")] = False,
    as_json: JsonOption = False,
) -> None:
    """Read one article in the terminal, from its published Markdown."""
    doc = _doc()
    matches = articles.candidates(doc["articles"], slug.strip().lower())
    if not matches:
        raise _fail(f"no article matches {slug!r} — try: fmind search {slug}")
    if len(matches) > 1:
        listed = ", ".join(matches[:10])
        raise _fail(f"{slug!r} matches {len(matches)} articles: {listed}")
    resolved = matches[0]
    try:
        markdown = load_article(resolved)
    except FmindError as error:
        raise _fail(str(error)) from error
    post = articles.by_slug(doc["articles"], resolved)
    if raw and not (as_json or ctx.find_root().params["as_json"]):
        _write(markdown)
        return
    payload = {"slug": resolved, "markdown": markdown, **(post or {})}
    _emit(ctx, render.article_body(markdown), payload, as_json=as_json, page=True)


@app.command()
def hire(ctx: typer.Context, as_json: JsonOption = False) -> None:
    """What can be booked right now."""
    doc = _doc()
    _emit(ctx, render.hire(doc), doc["services"], as_json=as_json)


@app.command()
def mcp(ctx: typer.Context) -> None:
    """Serve the website's remote MCP tools, resources, and prompts over stdio."""
    if ctx.find_root().params["as_json"]:
        raise typer.BadParameter("mcp uses protocol-only stdio; --json applies to portfolio commands")
    try:
        from fmind.mcp import serve
    except ImportError as error:
        raise _fail("MCP support is not installed; run: uv tool install --upgrade 'fmind[mcp]'") from error
    try:
        asyncio.run(serve())
    except FmindError as error:
        raise _fail(str(error)) from error
