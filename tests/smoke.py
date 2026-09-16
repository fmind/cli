"""Live website compatibility checks, shared by local use, monitoring, and CD."""

from __future__ import annotations

import asyncio
import json
import os
import sys

from mcp import Client, StdioServerParameters
from typer.testing import CliRunner

from fmind.api import _parse_profile, load_profile
from fmind.cli import app


async def smoke_mcp() -> None:
    """Exercise the advertised read-only surface through the real stdio bridge."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fmind", "mcp"],
        env={key: value for key, value in os.environ.items() if key == "FMIND_PROFILE_URL"},
    )
    async with asyncio.timeout(180), Client(params, cache=None, read_timeout_seconds=30) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        await client.list_resource_templates()
        if not (tools.tools and resources.resources and prompts.prompts):
            raise RuntimeError("MCP discovery returned an empty tools, resources, or prompts catalog")
        for tool in tools.tools:
            if not tool.annotations or not tool.annotations.read_only_hint:
                raise RuntimeError(f"MCP tool {tool.name} is no longer advertised as read-only")
            # The SDK validates results against live output schemas. Discover
            # article slugs from the profile instead of storing portfolio facts.
            arguments = {}
            if tool.name == "search_articles":
                arguments = {"query": "compatibility", "limit": 1}
            elif tool.name == "get_article":
                posts = load_profile()["articles"]
                if not posts:
                    raise RuntimeError("the website lists no article for the MCP read check")
                arguments = {"slug": posts[0]["slug"]}
            elif tool.name == "compare_llm_hosting":
                arguments = {"parameters": {}}
            print(f"check MCP tools/call {tool.name}", flush=True)
            result = await client.call_tool(tool.name, arguments)
            if result.is_error or not result.content:
                raise RuntimeError(f"MCP tools/call {tool.name} failed")
            print(f"ok    MCP tools/call {tool.name}")
        for resource in resources.resources:
            result = await client.read_resource(str(resource.uri))
            if not result.contents:
                raise RuntimeError(f"MCP resources/read {resource.name} returned no content")
            if resource.name == "profile":
                _parse_profile(result.contents[0].text.encode())
            print(f"ok    MCP resources/read {resource.name}")
        for prompt in prompts.prompts:
            arguments = {arg.name: "Compatibility check" for arg in prompt.arguments or [] if arg.required}
            result = await client.get_prompt(prompt.name, arguments)
            if not result.messages:
                raise RuntimeError(f"MCP prompts/get {prompt.name} returned no messages")
            print(f"ok    MCP prompts/get {prompt.name}")


def smoke_portfolio() -> None:
    """Render every command and check both JSON placements and raw Markdown."""
    runner = CliRunner()
    latest = runner.invoke(app, ["articles", "--limit", "1", "--json"])
    if latest.exit_code != 0:
        raise RuntimeError(f"could not read the live profile: {latest.output.strip()}")
    posts = json.loads(latest.stdout)
    if not posts:
        raise RuntimeError("the website lists no article to read")
    # Discover commands from Typer so a new section cannot silently miss the check.
    sections = [[command.name or command.callback.__name__] for command in app.registered_commands]
    commands = [command for command in sections if command[0] not in {"mcp", "read", "search"}]
    commands += [["search", posts[0]["slug"]], ["read", posts[0]["slug"]]]
    variants = [
        *commands,
        *([*command, "--json"] for command in commands),
        *(["--json", *command] for command in commands),
        ["read", posts[0]["slug"], "--raw"],
    ]
    failed: list[str] = []
    for command in variants:
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
            # CLI errors are safe one-line messages; don't print remote documents.
            print(result.stderr.strip() or f"exit {result.exit_code}; empty or invalid output", file=sys.stderr)
    if failed:
        raise RuntimeError(f"{len(failed)} portfolio check(s) failed")
    print(f"all {len(variants)} portfolio checks passed")


def main() -> int:
    """Report API and MCP failures independently so one cannot hide the other."""
    failed = False
    try:
        smoke_portfolio()
    except Exception as error:
        failed = True
        print(f"FAIL  API: {error}", file=sys.stderr)
    try:
        asyncio.run(smoke_mcp())
    except Exception as error:
        failed = True
        # Unexpected SDK/transport errors can carry private diagnostics.
        detail = str(error) if isinstance(error, RuntimeError) else type(error).__name__
        print(f"FAIL  MCP: {detail}", file=sys.stderr)
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
