"""Render sections of the portfolio document as terminal output."""

from __future__ import annotations

from typing import Any

from rich.console import Console, Group, RenderableType
from rich.markdown import Markdown
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

# Use the terminal palette so its light/dark theme owns colour contrast.
ACCENT = "bold blue"


def console(*, color: bool | None = None) -> Console:
    """Detect terminal colour and NO_COLOR unless explicitly overridden."""
    return Console(
        force_terminal=True if color is True else None,
        color_system="truecolor" if color is True else "auto",
        no_color=None if color is None else not color,
        highlight=False,
        markup=False,
    )


def _rows(pairs: list[tuple[str, RenderableType]]) -> Table:
    """Lay out aligned key/value rows without visible borders."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=ACCENT, width=11, overflow="fold")
    table.add_column(overflow="fold")
    for key, value in pairs:
        table.add_row(key, value)
    return table


def whoami(doc: dict[str, Any]) -> RenderableType:
    """Identity, featured experience, availability, and contact."""
    meta = doc["metadata"]
    experience = doc.get("experience") or []
    mission = Text("—")
    if experience:
        featured = experience[0]
        mission = Text(f"{featured['company']} — {featured['title']}")
    services = doc.get("services") or []
    status = Text()
    for index, service in enumerate(services):
        if index:
            status.append("\n")
        status.append(service["title"], style="bold")
        status.append(f" — {service['badge']}")
    return _rows(
        [
            ("Name", Text(f"{meta['name']} ({meta['alternate_name']})", style="bold")),
            ("Role", Text(meta["job_title"])),
            ("Headline", Text(meta["headline_primary"])),
            ("Experience", mission),
            ("Status", status),
            ("Contact", Text(meta["email"], style="underline")),
            ("Website", Text(meta["site_url"], style="underline")),
        ]
    )


def about(doc: dict[str, Any]) -> RenderableType:
    """The biography paragraphs."""
    return Group(*(Padding(Markdown(p, hyperlinks=False), (0, 0, 1, 0)) for p in doc["biography"]))


def skills(doc: dict[str, Any]) -> RenderableType:
    """Show expertise without inventing command-line options or local labels."""
    return Group(
        *(
            Padding(Group(Text(card["title"], style="bold"), Text(card["description"])), (0, 0, 1, 0))
            for card in doc["expertise"]
        )
    )


def experiences(doc: dict[str, Any]) -> RenderableType:
    """Engagements in the order published by the website."""
    blocks: list[RenderableType] = []
    for job in doc["experience"]:
        head = Text(job["company"].upper(), style=ACCENT)
        body = Group(
            head,
            Text(job["title"], style="bold"),
            Text(job["description"]),
            Text("  ".join(job["tags"])),
        )
        blocks.append(Padding(body, (0, 0, 1, 0)))
    return Group(*blocks)


def community(doc: dict[str, Any]) -> RenderableType:
    """Ambassador and advisory roles, with their published links."""
    return Group(
        *(
            Padding(
                Group(
                    Text(role["organization"], style=ACCENT),
                    Text(role["role"], style="bold"),
                    Text(role["description"]),
                    Text(role["url"], style="underline"),
                ),
                (0, 0, 1, 0),
            )
            for role in doc["leadership"]
        )
    )


def certifications(doc: dict[str, Any]) -> RenderableType:
    """Credentials, doctorate, and specializations with published evidence."""
    blocks: list[RenderableType] = []
    for badge in doc["certifications"]:
        state = "active" if badge["active"] else "past"
        blocks.append(
            Padding(
                Group(
                    Text(f"[{state}] {badge['title']}", style=ACCENT),
                    Text(badge["issuer"]),
                    Text(badge["url"], style="underline"),
                ),
                (0, 0, 1, 0),
            )
        )
    thesis = doc["thesis"]
    blocks.append(
        Padding(
            Group(
                Text(thesis["title"], style=ACCENT),
                Text(thesis["institution_details"]),
                Text(thesis["url"], style="underline"),
            ),
            (0, 0, 1, 0),
        )
    )
    if doc["specializations"]:
        blocks.append(Text("SPECIALIZATIONS", style=ACCENT))
    for spec in doc["specializations"]:
        blocks.append(
            Padding(
                Group(
                    Text(spec["title"], style="bold"),
                    Text(spec["issuer_details"]),
                    Text(spec["url"], style="underline"),
                ),
                (1, 0, 0, 0),
            )
        )
    return Group(*blocks)


def projects(doc: dict[str, Any], *, limit: int = 6) -> RenderableType:
    """Open-source repositories and video series."""
    items = [(p["title"], p["description"], p["href"]) for p in doc["open_source"]]
    items += [(v["title"], v["description"], v["url"]) for v in doc["youtube_series"]]
    blocks = [
        Padding(Group(Text(title, style="bold"), Text(description), Text(url, style="underline")), (0, 0, 1, 0))
        for title, description, url in items[: max(limit, 0)]
    ]
    return Group(*blocks)


def articles(posts: list[dict[str, Any]], *, footer: str = "") -> RenderableType:
    """A list of articles, one block each, with `fmind read` slugs kept visible."""
    blocks: list[RenderableType] = []
    for post in posts:
        head = Text(post["date"][:10], style=ACCENT)
        head.append(f"  {post['reading_minutes']} min")
        head.append(f"  {'  '.join(post['tags'])}")
        body = Text("fmind read ")
        body.append(post["slug"], style="bold")
        blocks.append(Padding(Group(head, Text(post["title"], style="bold"), body), (0, 0, 1, 0)))
    if not blocks:
        return Text("no article matches")
    return Group(*blocks, Text(footer)) if footer else Group(*blocks)


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
        Text(thesis["title"], style="bold"),
        Text(thesis["institution_details"]),
        Text(thesis["description"]),
        Text(thesis["url"], style="underline"),
    )
    parts: list[RenderableType] = [Padding(head, (0, 0, 1, 0))]
    for link in thesis.get("links") or []:
        row = Text("  ")
        row.append(link["label"])
        row.append(f"  {link['url']}", style="underline")
        parts.append(row)
    if thesis.get("links"):
        parts.append(Text())
    parts.append(Text("PUBLICATIONS", style=ACCENT))
    for paper in doc["papers"]:
        body = Group(
            Text(paper["title"], style="bold"),
            Text(paper["venue"]),
            Text(paper["url"], style="underline"),
        )
        parts.append(Padding(body, (1, 0, 0, 0)))
    return Group(*parts)


def sites(doc: dict[str, Any]) -> RenderableType:
    """Interactive tools published alongside the writing."""
    blocks = [
        Padding(
            Group(
                Text(page["title"], style="bold"),
                Text(page["description"]),
                Text(f"for {page['audience']}"),
                Text(page["url"], style="underline"),
            ),
            (0, 0, 1, 0),
        )
        for page in doc["site_pages"]
    ]
    return Group(*blocks) if blocks else Text("no interactive site published")


def hire(doc: dict[str, Any]) -> RenderableType:
    """What can be booked right now."""
    blocks: list[RenderableType] = []
    for service in doc["services"]:
        blocks.append(
            Padding(
                Group(
                    Text(service["title"], style="bold"),
                    Text(service["description"]),
                    Text(service["badge"], style="bold"),
                    Text(service["cta_url"], style="underline"),
                ),
                (0, 0, 1, 0),
            )
        )
    return Group(*blocks)
