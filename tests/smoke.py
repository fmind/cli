"""Exercise every command against the live site.

Network-dependent, so it is a separate `mise run smoke` rather than part of `test`.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters
from typer.testing import CliRunner

from fmind.cli import app

SECTIONS = [
    ["whoami"],
    ["about"],
    ["skills"],
    ["experiences"],
    ["certifications"],
    ["community"],
    ["papers"],
    ["projects"],
    ["sites"],
    ["articles"],
    ["hire"],
    ["search", "agent"],
]


async def smoke_mcp() -> None:
    """Prove stdio discovery and a tool call through the actual remote server."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from fmind.cli import app; app()", "mcp"],
        env={key: value for key, value in os.environ.items() if key == "FMIND_PROFILE_URL"},
    )
    async with Client(params, cache=None, read_timeout_seconds=30) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        result = await client.call_tool("get_profile", {})
        if not (tools.tools and resources.resources and prompts.prompts and result.content) or result.is_error:
            raise RuntimeError("remote MCP discovery or get_profile failed")


def main() -> int:
    """Run each section against the live profile and report failures."""
    runner = CliRunner()
    failed: list[str] = []
    latest = runner.invoke(app, ["articles", "--limit", "1", "--json"])
    if latest.exit_code != 0:
        print(f"FAIL  could not read the live profile: {latest.output.strip()}", file=sys.stderr)
        return 1
    posts = json.loads(latest.stdout)
    if not posts:
        print("FAIL  the website lists no article to read", file=sys.stderr)
        return 1
    sections = [*SECTIONS, ["read", posts[0]["slug"]]]
    commands = [*sections, *([*command, "--json"] for command in sections)]
    for command in commands:
        result = runner.invoke(app, ["--no-color", *command])
        ok = result.exit_code == 0 and bool(result.stdout.strip()) and not result.stderr
        if ok and "--json" in command:
            try:
                json.loads(result.stdout)
            except ValueError:
                ok = False
        label = " ".join(command)
        print(f"{'ok  ' if ok else 'FAIL'}  fmind {label}")
        if not ok:
            failed.append(label)
            print(result.output.strip(), file=sys.stderr)
    try:
        asyncio.run(smoke_mcp())
        print("ok    fmind mcp (stdio discovery and remote get_profile)")
    except Exception:
        failed.append("mcp")
        print("FAIL  fmind mcp: remote stdio smoke failed", file=sys.stderr)
    if failed:
        print(f"\n{len(failed)} command(s) failed: {', '.join(failed)}", file=sys.stderr)
        return 1
    print(f"\nall {len(commands)} portfolio checks and the MCP bridge passed against the live site")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
