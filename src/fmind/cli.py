"""Command surface, mirroring the sections of www.fmind.dev."""

from __future__ import annotations

import json
import sys
from typing import Annotated, Any

import typer
from rich.console import RenderableType

from fmind import __version__, articles, render
from fmind.api import FmindError, load_article, load_profile

app = typer.Typer(
    name="fmind",
    help="Read Médéric Hurier's (Fmind) portfolio from the terminal. Every command renders the live "
    "profile published at https://www.fmind.dev/api/profile.",
    add_completion=False,
    no_args_is_help=True,
    rich_markup_mode=None,
)

_STATE: dict[str, Any] = {"refresh": False, "json": False, "color": True}


def _version(value: bool) -> None:
    if value:
        typer.echo(f"fmind {__version__}")
        raise typer.Exit


@app.callback()
def main(
    refresh: Annotated[bool, typer.Option("--refresh", help="Ignore the cached copy and fetch it again.")] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Print the raw section as JSON instead of prose.")] = False,
    color: Annotated[bool, typer.Option("--color/--no-color", help="Force or suppress ANSI colour.")] = True,
    _v: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True, help="Show the version.")] = False,
) -> None:
    """Store the global options for the section commands."""
    _STATE.update(refresh=refresh, json=as_json, color=color)


def _fail(message: str) -> typer.Exit:
    """Report a clear one-line error on stderr and end the command."""
    typer.secho(f"fmind: {message}", fg="red", err=True)
    return typer.Exit(code=1)


def _doc() -> dict[str, Any]:
    """Load the profile, reporting a clear error instead of a traceback."""
    try:
        return load_profile(refresh=bool(_STATE["refresh"]))
    except FmindError as error:
        raise _fail(str(error)) from error


def _emit(body: RenderableType, payload: Any, *, banner: dict[str, Any] | None = None) -> None:
    """Print either the rendered section or its raw JSON."""
    if _STATE["json"]:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
        return
    out = render.console(color=bool(_STATE["color"]))
    if banner is not None:
        out.print(render.banner(banner))
        out.print()
    out.print(body)


@app.command()
def whoami() -> None:
    """Name, current mission, contact and availability."""
    doc = _doc()
    _emit(render.whoami(doc), {"metadata": doc["metadata"], "services": doc["services"]}, banner=doc)


@app.command()
def about() -> None:
    """The biography, as published on the site."""
    doc = _doc()
    _emit(render.about(doc), doc["biography"])


@app.command()
def skills() -> None:
    """Core expertise, laid out like a usage screen."""
    doc = _doc()
    _emit(render.skills(doc), doc["expertise"])


@app.command()
def work() -> None:
    """Engagements, current one first."""
    doc = _doc()
    _emit(render.work(doc), doc["experience"])


@app.command()
def community() -> None:
    """Ambassador and advisory roles."""
    doc = _doc()
    _emit(render.community(doc), doc["leadership"])


@app.command()
def cert(
    verify: Annotated[bool, typer.Option("--verify", help="List only credentials that are still active.")] = False,
) -> None:
    """Certifications, the PhD, and specializations."""
    doc = _doc()
    payload = [c for c in doc["certifications"] if c["active"]] if verify else doc["certifications"]
    _emit(render.cert(doc, verify=verify), payload)


@app.command()
def papers() -> None:
    """The doctorate and the peer-reviewed publications."""
    doc = _doc()
    _emit(render.papers(doc), {"thesis": doc["thesis"], "papers": doc["papers"]})


@app.command()
def project(
    top: Annotated[int, typer.Option("--top", min=1, max=50, help="How many projects to show.")] = 6,
) -> None:
    """Open-source repositories and video series."""
    doc = _doc()
    _emit(render.project(doc, top=top), (doc["open_source"] + doc["youtube_series"])[:top])


@app.command()
def sites() -> None:
    """Interactive tools published alongside the writing."""
    doc = _doc()
    _emit(render.sites(doc), doc["site_pages"])


@app.command()
def article(
    limit: Annotated[int, typer.Option("--limit", min=1, max=200, help="How many articles to show.")] = 6,
) -> None:
    """The most recent writing."""
    doc = _doc()
    posts = articles.latest(doc["articles"], limit=limit)
    footer = f"{len(doc['articles'])} published · {doc['metadata']['site_url']}/articles/"
    _emit(render.articles(posts, footer=footer), posts)


@app.command()
def search(
    query: Annotated[str, typer.Argument(help="Terms to match against titles, summaries, tags and slugs.")],
    tag: Annotated[str | None, typer.Option("--tag", help="Restrict to one of the site's tags, such as Agent.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, max=200, help="How many matches to show.")] = 10,
) -> None:
    """Find articles by term, newest match first."""
    doc = _doc()
    found = articles.search(doc["articles"], query, tag=tag, limit=limit)
    footer = f"{len(found)} shown · {len(doc['articles'])} published · fmind read <slug> opens one"
    _emit(render.articles(found, footer=footer), found)


@app.command()
def read(
    slug: Annotated[str, typer.Argument(help="Article slug, or enough of it to be unambiguous.")],
    raw: Annotated[bool, typer.Option("--raw", help="Print the Markdown source instead of rendering it.")] = False,
) -> None:
    """Read one article in the terminal, from its published Markdown."""
    doc = _doc()
    matches = articles.candidates(doc["articles"], slug.strip().lower())
    if not matches:
        raise _fail(f"no article matches {slug!r} — try: fmind search {slug}")
    if len(matches) > 1:
        listed = "\n  ".join(matches[:10])
        raise _fail(f"{slug!r} matches {len(matches)} articles:\n  {listed}")
    resolved = matches[0]
    try:
        markdown = load_article(resolved, refresh=bool(_STATE["refresh"]))
    except FmindError as error:
        raise _fail(str(error)) from error
    post = articles.by_slug(doc["articles"], resolved)
    if raw and not _STATE["json"]:
        sys.stdout.write(markdown)
        return
    _emit(render.article_body(markdown), {"slug": resolved, "markdown": markdown, **(post or {})})


@app.command()
def hire() -> None:
    """What can be booked right now."""
    doc = _doc()
    _emit(render.hire(doc), doc["services"])
