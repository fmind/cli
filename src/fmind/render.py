"""Render sections of the portfolio document as terminal output."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.markdown import Markdown
from rich.padding import Padding
from rich.segment import Segment
from rich.style import Style
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


class Trimmed:
    """Drop the padding Rich adds at line ends, which only shows once output is redirected."""

    def __init__(self, renderable: RenderableType) -> None:
        self.renderable = renderable

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        for line in Segment.split_lines(console.render(self.renderable, options)):
            yield from _rstrip(line)
            yield Segment.line()


def _rstrip(line: list[Segment]) -> Iterable[Segment]:
    """Remove trailing whitespace from one rendered line, keeping control codes."""
    while line and not line[-1].control and not line[-1].text.rstrip():
        line.pop()
    if line and not line[-1].control:
        text, style, _ = line[-1]
        line[-1] = Segment(text.rstrip(), style)
    return line


def _link(url: str) -> Text:
    """A published URL on one logical line: folding it would break copying and clicking."""
    # Terminals that support OSC 8 make it clickable; the text stays the literal URL.
    style = Style(underline=True, link=url) if url.startswith(("https://", "http://", "mailto:")) else "underline"
    return Text(url, style=style, no_wrap=True, overflow="ignore")


def _entry(*lines: RenderableType) -> Group:
    """One stacked entry followed by a blank line, without padding that would crop links."""
    return Group(*lines, Text())


def _listing(blocks: Sequence[RenderableType], empty: str) -> RenderableType:
    """The entries, or one line saying so when the website publishes none."""
    return Group(*blocks) if blocks else Text(empty)


def _rows(pairs: list[tuple[str, RenderableType]]) -> Table:
    """Lay out aligned key/value rows without visible borders."""
    table = Table.grid(padding=(0, 2))
    table.add_column(style=ACCENT, width=11, overflow="fold")
    table.add_column(overflow="fold")
    for key, value in pairs:
        table.add_row(key, value)
    return table


def whoami(doc: dict[str, Any]) -> RenderableType:
    """Identity, location, featured experience, availability, contact, and social profiles."""
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
    return Group(
        _rows(
            [
                ("Name", Text(f"{meta['name']} ({meta['alternate_name']})", style="bold")),
                ("Role", Text(meta["job_title"])),
                ("Headline", Text("\n".join(filter(None, (meta["headline_primary"], meta["headline_secondary"]))))),
                ("Location", Text(meta["work_location"])),
                ("Experience", mission),
                ("Status", status),
            ]
        ),
        # Table cells crop even no-wrap links. Keep these outside the grid,
        # with the same 11-character label and two-space gap.
        *(
            Text.assemble((f"{label:<13}", ACCENT), _link(value), no_wrap=True, overflow="ignore")
            for label, value in (
                ("Contact", meta["email"]),
                ("Website", meta["site_url"]),
                *((social["name"], social["url"]) for social in meta["socials"]),
            )
        ),
    )


def about(doc: dict[str, Any]) -> RenderableType:
    """The biography paragraphs."""
    return Group(*(Padding(Markdown(p, hyperlinks=False), (0, 0, 1, 0)) for p in doc["biography"]))


def skills(doc: dict[str, Any]) -> RenderableType:
    """Show expertise without inventing command-line options or local labels."""
    blocks = [_entry(Text(card["title"], style="bold"), Text(card["description"])) for card in doc["expertise"]]
    return _listing(blocks, "no expertise published")


def experiences(doc: dict[str, Any]) -> RenderableType:
    """Engagements in the order published by the website."""
    blocks = [
        _entry(
            Text(job["company"].upper(), style=ACCENT),
            Text(job["title"], style="bold"),
            Text(job["description"]),
            Text("  ".join(job["tags"])),
        )
        for job in doc["experience"]
    ]
    return _listing(blocks, "no experience published")


def community(doc: dict[str, Any]) -> RenderableType:
    """Ambassador and advisory roles, with their published links."""
    blocks = [
        _entry(
            Text(role["organization"], style=ACCENT),
            Text(role["role"], style="bold"),
            Text(role["description"]),
            _link(role["url"]),
        )
        for role in doc["leadership"]
    ]
    return _listing(blocks, "no community role published")


def certifications(doc: dict[str, Any]) -> RenderableType:
    """Credentials, doctorate, and specializations with published evidence."""
    blocks: list[RenderableType] = []
    for badge in doc["certifications"]:
        state = "active" if badge["active"] else "past"
        blocks.append(
            _entry(Text(f"[{state}] {badge['title']}", style=ACCENT), Text(badge["issuer"]), _link(badge["url"]))
        )
    thesis = doc["thesis"]
    blocks.append(
        _entry(Text(thesis["title"], style=ACCENT), Text(thesis["institution_details"]), _link(thesis["url"]))
    )
    if doc["specializations"]:
        blocks += [Text("SPECIALIZATIONS", style=ACCENT), Text()]
    blocks += [
        _entry(Text(spec["title"], style="bold"), Text(spec["issuer_details"]), _link(spec["url"]))
        for spec in doc["specializations"]
    ]
    return Group(*blocks)


def projects(doc: dict[str, Any], *, limit: int = 6) -> RenderableType:
    """Open-source repositories, then video series; `limit` bounds each list."""
    count = max(limit, 0)
    blocks: list[RenderableType] = [
        _entry(Text(project["title"], style="bold"), Text(project["description"]), _link(project["href"]))
        for project in doc["open_source"][:count]
    ]
    series = doc["youtube_series"][:count]
    if series:
        blocks += [Text("VIDEO SERIES", style=ACCENT), Text()]
    blocks += [
        _entry(Text(video["title"], style="bold"), Text(video["description"]), _link(video["url"])) for video in series
    ]
    return _listing(blocks, "no project published")


def articles(posts: list[dict[str, Any]], *, footer: str = "") -> RenderableType:
    """A list of articles, one block each, with `fmind read` slugs kept visible."""
    blocks: list[RenderableType] = []
    for post in posts:
        head = Text(post["date"][:10], style=ACCENT)
        head.append(f"  {post['reading_minutes']} min")
        head.append(f"  {'  '.join(post['tags'])}")
        body = Text("fmind read ")
        body.append(post["slug"], style="bold")
        blocks.append(_entry(head, Text(post["title"], style="bold"), body))
    if not blocks:
        return Text("no article matches")
    return Group(*blocks, Text(footer)) if footer else Group(*blocks)


def tags(doc: dict[str, Any]) -> RenderableType:
    """The site's article tags, each with its article count and the search that lists them."""
    blocks: list[RenderableType] = []
    for tag in doc["tags"]:
        # Case-insensitive, like `fmind search --tag`.
        name = tag["name"].lower()
        count = sum(name in {t.lower() for t in post["tags"]} for post in doc["articles"])
        hint = Text(f"{count} article{'' if count == 1 else 's'} · fmind search --tag ")
        hint.append(tag["name"], style="bold")
        blocks.append(_entry(Text(tag["name"], style=ACCENT), Text(tag["description"]), hint))
    return _listing(blocks, "no tag published")


def news(editions: list[dict[str, Any]], *, footer: str = "") -> RenderableType:
    """Daily news editions, each with its curated links."""
    blocks: list[RenderableType] = []
    for edition in editions:
        blocks += [Text(edition["title"], style=ACCENT), _link(edition["url"]), Text()]
        blocks += [
            _entry(Text(item["title"], style="bold"), Text(item["description"]), _link(item["url"]))
            for item in edition["items"]
        ]
    if not blocks:
        return Text("no news edition matches")
    return Group(*blocks, Text(footer)) if footer else Group(*blocks)


def article_body(markdown: str) -> RenderableType:
    """One article, rendered from its published Markdown source.

    The source already opens with the title, summary, date, reading time, tags and
    canonical URL, so nothing is prepended here.
    """
    return Markdown(markdown, code_theme="ansi_light", hyperlinks=False)


def papers(doc: dict[str, Any]) -> RenderableType:
    """The doctorate and the peer-reviewed record behind it."""
    thesis = doc["thesis"]
    parts: list[RenderableType] = [
        _entry(
            Text(thesis["title"], style="bold"),
            Text(thesis["institution_details"]),
            Text(thesis["description"]),
            _link(thesis["url"]),
        )
    ]
    for link in thesis.get("links") or []:
        row = Text(f"  {link['label']}  ", no_wrap=True, overflow="ignore")
        row.append_text(_link(link["url"]))
        parts.append(row)
    if thesis.get("links"):
        parts.append(Text())
    parts += [Text("PUBLICATIONS", style=ACCENT), Text()]
    for paper in doc["papers"]:
        lines: list[RenderableType] = [Text(paper["title"], style="bold"), Text(paper["venue"]), _link(paper["url"])]
        if paper["code"]:
            code = Text(f"  {paper['code_label'] or 'Code'}  ", no_wrap=True, overflow="ignore")
            code.append_text(_link(paper["code"]))
            lines.append(code)
        parts.append(_entry(*lines))
    return Group(*parts)


def sites(doc: dict[str, Any]) -> RenderableType:
    """Interactive tools published alongside the writing."""
    blocks = [
        _entry(
            Text(page["title"], style="bold"),
            Text(page["description"]),
            Text(f"for {page['audience']}"),
            _link(page["url"]),
        )
        for page in doc["site_pages"]
    ]
    return _listing(blocks, "no interactive site published")


def hire(doc: dict[str, Any]) -> RenderableType:
    """What can be booked right now."""
    blocks = [
        _entry(
            Text(service["title"], style="bold"),
            Text(service["description"]),
            Text(service["badge"], style="bold"),
            _link(service["cta_url"]),
        )
        for service in doc["services"]
    ]
    return _listing(blocks, "no service published")
