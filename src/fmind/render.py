"""Render sections of the portfolio document as terminal output."""

from __future__ import annotations

from typing import Any

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

ACCENT = "bold #00ff41"
HI = "bold #ccffd9"
DIM = "#57a86e"
FLAG = "#7dffab"
ERR = "#ff7a5c"

WORDMARK = (
    "█▀▀▀  █▄ ▄█  ▀█▀  █▄  █  █▀▀▄ ",
    "█▄▄   █ ▀ █   █   █ █ █  █   █",
    "█     █   █   █   █  ██  █   █",
    "█     █   █  ▄█▄  █   █  █▄▄▀ ",
)


def console(*, color: bool | None = None) -> Console:
    """Detect terminal colour and NO_COLOR unless explicitly overridden."""
    return Console(
        force_terminal=True if color is True else None,
        color_system="truecolor" if color is True else "auto",
        no_color=None if color is None else not color,
        highlight=False,
        markup=False,
    )


def _rows(pairs: list[tuple[str, RenderableType]], key_width: int = 11) -> Table:
    """Lay out aligned key/value rows without visible borders."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=ACCENT, width=key_width, overflow="fold")
    table.add_column(overflow="fold")
    for key, value in pairs:
        table.add_row(key, value)
    return table


def banner(doc: dict[str, Any]) -> RenderableType:
    """The wordmark beside the name, role and headline."""
    meta = doc["metadata"]
    mark = Text("\n".join(WORDMARK), style=ACCENT)
    identity = Group(
        Text(meta["name"], style=HI),
        Text(meta["job_title"], style="#00ff41"),
        Text(meta["headline_primary"], style=DIM),
    )
    side = Table.grid(padding=(0, 3))
    side.add_column(no_wrap=True)
    side.add_column(overflow="fold")
    side.add_row(mark, identity)
    return side


def whoami(doc: dict[str, Any]) -> RenderableType:
    """Identity, current mission, availability, and contact."""
    meta = doc["metadata"]
    experience = doc.get("experience") or []
    mission = Text("—", style=DIM)
    if experience:
        current = experience[0]
        mission = Text(f"{current['company']} — {current['title']}", style="#74e492")
    services = doc.get("services") or []
    status = Text()
    for index, service in enumerate(services):
        open_now = service.get("badge_type") != "error"
        if index:
            status.append("\n")
        status.append("● ", style="#00ff41" if open_now else ERR)
        status.append(service["title"], style=HI)
        status.append(f" — {service['badge']}", style=DIM)
    return _rows(
        [
            ("Name", Text(f"{meta['name']} ({meta['alternate_name']})", style=HI)),
            ("Role", Text(meta["job_title"], style="#74e492")),
            ("Mission", mission),
            ("Status", status),
            ("Contact", Text(meta["email"], style=FLAG)),
            ("Website", Text(meta["site_url"], style=FLAG)),
        ]
    )


def about(doc: dict[str, Any]) -> RenderableType:
    """The biography paragraphs."""
    return Group(*(Padding(Markdown(p, hyperlinks=False), (0, 0, 1, 0)) for p in doc["biography"]))


def skills(doc: dict[str, Any]) -> RenderableType:
    """Show expertise without inventing command-line options or local labels."""
    return Group(
        *(
            Padding(Group(Text(card["title"], style=HI), Text(card["description"], style=DIM)), (0, 0, 1, 0))
            for card in doc["expertise"]
        )
    )


def experiences(doc: dict[str, Any]) -> RenderableType:
    """Engagements, current one first."""
    blocks: list[RenderableType] = []
    for index, job in enumerate(doc["experience"]):
        head = Text(job["company"].upper(), style=ACCENT)
        if index == 0:
            head.append(" · current", style=DIM)
        body = Group(
            head,
            Text(job["title"], style=HI),
            Text(job["description"], style=DIM),
            Text("  ".join(job["tags"]), style=FLAG),
        )
        blocks.append(Padding(body, (0, 0, 1, 0)))
    return Group(*blocks)


def community(doc: dict[str, Any]) -> RenderableType:
    """Ambassador and advisory roles."""
    return _rows(
        [
            (r["organization"], Group(Text(r["role"], style=HI), Text(r["description"], style=DIM)))
            for r in doc["leadership"]
        ],
        key_width=28,
    )


def certifications(doc: dict[str, Any]) -> RenderableType:
    """Credentials, the doctorate that backs them, and the specializations."""
    table = Table.grid(padding=(0, 2))
    table.add_column(width=8, no_wrap=True)
    table.add_column(overflow="fold")
    for badge in doc["certifications"]:
        active = bool(badge["active"])
        # The same two words the website spells, so colour never carries the state.
        state = Text("[active]" if active else "[past]", style="#00ff41" if active else DIM)
        body = Text(badge["title"], style=HI if active else "#74e492")
        body.append(f" — {badge['issuer']}", style=DIM)
        table.add_row(state, body)
    degree = Text(doc["thesis"]["title"], style=HI)
    degree.append(f" — {doc['thesis']['institution_details']}", style=DIM)
    specs = Text("\n".join(f"  {s['title']} — {s['issuer_details']}" for s in doc["specializations"]), style=DIM)
    return Group(
        table,
        Padding(degree, (1, 0, 0, 0)),
        Padding(Group(Text("SPECIALIZATIONS", style=DIM), specs), (1, 0, 0, 0)),
    )


def projects(doc: dict[str, Any], *, limit: int = 6) -> RenderableType:
    """Open-source repositories and video series."""
    items = [(p["title"], p["description"], p["href"]) for p in doc["open_source"]]
    items += [(v["title"], v["description"], v["url"]) for v in doc["youtube_series"]]
    blocks = [
        Padding(Group(Text(title, style=HI), Text(description, style=DIM), Text(url, style=FLAG)), (0, 0, 1, 0))
        for title, description, url in items[: max(limit, 0)]
    ]
    return Group(*blocks)


def articles(posts: list[dict[str, Any]], *, footer: str = "") -> RenderableType:
    """A list of articles, one block each, with `fmind read` slugs kept visible."""
    blocks: list[RenderableType] = []
    for post in posts:
        head = Text(post["date"][:10], style=ACCENT)
        head.append(f"  {post['reading_minutes']} min", style=DIM)
        head.append(f"  {'  '.join(post['tags'])}", style=FLAG)
        body = Text("fmind read ", style=DIM)
        body.append(post["slug"], style=FLAG)
        blocks.append(Padding(Group(head, Text(post["title"], style=HI), body), (0, 0, 1, 0)))
    if not blocks:
        return Text("no article matches", style=DIM)
    return Group(*blocks, Text(footer, style=DIM)) if footer else Group(*blocks)


def article_body(markdown: str) -> RenderableType:
    """One article, rendered from its published Markdown source.

    The source already opens with the title, summary, date, reading time, tags and
    canonical URL, so nothing is prepended here.
    """
    return Markdown(markdown, code_theme="ansi_dark", hyperlinks=False)


def papers(doc: dict[str, Any]) -> RenderableType:
    """The doctorate and the peer-reviewed record behind it."""
    thesis = doc["thesis"]
    head = Group(
        Text(thesis["title"], style=HI),
        Text(thesis["institution_details"], style="#74e492"),
        Text(thesis["description"], style=DIM),
        Text(thesis["url"], style=FLAG),
    )
    parts: list[RenderableType] = [Padding(head, (0, 0, 1, 0))]
    for link in thesis.get("links") or []:
        row = Text("  ", style=DIM)
        row.append(link["label"], style="#74e492")
        row.append(f"  {link['url']}", style=FLAG)
        parts.append(row)
    if thesis.get("links"):
        parts.append(Text())
    parts.append(Text("PUBLICATIONS", style=ACCENT))
    for paper in doc["papers"]:
        body = Group(
            Text(paper["title"], style=HI),
            Text(paper["venue"], style=DIM),
            Text(paper["url"], style=FLAG),
        )
        parts.append(Padding(body, (1, 0, 0, 0)))
    return Group(*parts)


def sites(doc: dict[str, Any]) -> RenderableType:
    """Interactive tools published alongside the writing."""
    blocks = [
        Padding(
            Group(
                Text(page["title"], style=HI),
                Text(page["description"], style=DIM),
                Text(f"for {page['audience']}", style="#74e492"),
                Text(page["url"], style=FLAG),
            ),
            (0, 0, 1, 0),
        )
        for page in doc["site_pages"]
    ]
    return Group(*blocks) if blocks else Text("no interactive site published", style=DIM)


def hire(doc: dict[str, Any]) -> RenderableType:
    """What can be booked right now."""
    blocks: list[RenderableType] = []
    for service in doc["services"]:
        open_now = service.get("badge_type") != "error"
        state = Text("● ", style="#00ff41" if open_now else ERR)
        state.append(service["badge"], style="#00ff41" if open_now else ERR)
        blocks.append(
            Padding(
                Group(
                    Text(service["title"], style=HI),
                    Text(service["description"], style=DIM),
                    state,
                    Text(service["cta_url"], style=FLAG),
                ),
                (0, 0, 1, 0),
            )
        )
    return Group(*blocks)
