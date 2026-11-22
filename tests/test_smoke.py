"""Offline regressions for the live compatibility checker itself."""

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, create_autospec

import mcp_types as types
import pytest
from mcp import Client

from tests import smoke


def _tool(name: str, *, read_only: bool = True) -> types.Tool:
    return types.Tool(
        name=name,
        input_schema={"type": "object"},
        annotations=types.ToolAnnotations(read_only_hint=read_only),
    )


@pytest.fixture
def remote(monkeypatch: pytest.MonkeyPatch, document: dict[str, Any]) -> Any:
    client = create_autospec(Client, instance=True, spec_set=True)
    names = [
        "get_profile",
        "search_articles",
        "get_article",
        "search_news",
        "get_news",
        "compare_llm_hosting",
        "compare_mcp_context_cost",
    ]
    client.list_tools.return_value = types.ListToolsResult(tools=[_tool(name) for name in names])
    client.list_resources.return_value = types.ListResourcesResult(
        resources=[types.Resource(name="profile", uri="fmind://profile")]
    )
    client.list_prompts.return_value = types.ListPromptsResult(
        prompts=[
            types.Prompt(
                name="brief",
                arguments=[types.PromptArgument(name="audience", required=True)],
            )
        ]
    )
    client.list_resource_templates.return_value = types.ListResourceTemplatesResult(resource_templates=[])
    client.call_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="result")],
        is_error=False,
    )
    client.read_resource.return_value = types.ReadResourceResult(
        contents=[types.TextResourceContents(uri="fmind://profile", text=json.dumps(document))]
    )
    client.get_prompt.return_value = types.GetPromptResult(
        messages=[types.PromptMessage(role="user", content=types.TextContent(type="text", text="prompt"))]
    )
    client.__aenter__.return_value = client
    monkeypatch.setattr(smoke, "Client", lambda *_args, **_kwargs: client)
    monkeypatch.setattr(smoke, "load_profile", lambda: {"articles": [{"slug": "fresh-article"}]})
    monkeypatch.setattr(smoke, "load_news", lambda: {"editions": [{"slug": "2024-08-16"}]})
    return client


def test_mcp_checks_articles_news_and_calculator_with_live_inputs(remote: Any) -> None:
    asyncio.run(smoke.smoke_mcp())

    assert [call.args for call in remote.call_tool.await_args_list] == [
        ("get_profile", {}),
        ("search_articles", {"query": "compatibility", "limit": 1}),
        ("get_article", {"slug": "fresh-article"}),
        ("search_news", {"query": "compatibility", "limit": 1}),
        ("get_news", {"slug": "2024-08-16"}),
        ("compare_llm_hosting", {"parameters": {}}),
        ("compare_mcp_context_cost", {}),
    ]
    remote.get_prompt.assert_awaited_once_with("brief", {"audience": "Compatibility check"})


@pytest.mark.parametrize("field", ["tools", "resources", "prompts", "resource_templates"])
def test_mcp_checks_later_catalog_pages(remote: Any, field: str) -> None:
    listing = getattr(remote, f"list_{field}")
    first = listing.return_value.model_copy(update={"next_cursor": "page-two"})
    listing.side_effect = [first, RuntimeError("second page failed")]
    with pytest.raises(RuntimeError, match="second page failed"):
        asyncio.run(smoke.smoke_mcp())
    assert [call.kwargs for call in listing.await_args_list] == [{"cursor": None}, {"cursor": "page-two"}]


def test_mcp_exercises_entries_on_later_pages(remote: Any) -> None:
    first = remote.list_tools.return_value.model_copy(update={"next_cursor": "page-two"})
    remote.list_tools.side_effect = [
        first,
        types.ListToolsResult(tools=[_tool("later-tool")]),
    ]
    asyncio.run(smoke.smoke_mcp())
    remote.call_tool.assert_any_await("later-tool", {})


def test_mcp_rejects_repeated_pagination_cursors(remote: Any) -> None:
    remote.list_tools.return_value = remote.list_tools.return_value.model_copy(update={"next_cursor": "repeated"})
    with pytest.raises(RuntimeError, match="repeated a pagination cursor"):
        asyncio.run(smoke.smoke_mcp())
    assert remote.list_tools.await_count == 2


def test_mcp_rejects_non_readonly_tools(remote: Any) -> None:
    remote.list_tools.return_value = types.ListToolsResult(tools=[_tool("mutate", read_only=False)])
    with pytest.raises(RuntimeError, match="no longer advertised as read-only"):
        asyncio.run(smoke.smoke_mcp())


def test_mcp_rejects_empty_catalog(remote: Any) -> None:
    remote.list_prompts.return_value = types.ListPromptsResult(prompts=[])
    with pytest.raises(RuntimeError, match="empty tools, resources, or prompts catalog"):
        asyncio.run(smoke.smoke_mcp())


def test_mcp_rejects_tool_error_result(remote: Any) -> None:
    remote.call_tool.return_value = types.CallToolResult(
        content=[types.TextContent(type="text", text="boom")],
        is_error=True,
    )
    with pytest.raises(RuntimeError, match="tools/call get_profile failed"):
        asyncio.run(smoke.smoke_mcp())


def test_mcp_rejects_non_text_profile_resource(remote: Any) -> None:
    remote.read_resource.return_value = types.ReadResourceResult(
        contents=[types.BlobResourceContents(uri="fmind://profile", blob="YWJj")]
    )
    with pytest.raises(RuntimeError, match="no longer text"):
        asyncio.run(smoke.smoke_mcp())


@pytest.mark.usefixtures("offline")
def test_checks_every_portfolio_variant(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    mcp = AsyncMock()
    monkeypatch.setattr(smoke, "smoke_mcp", mcp)
    assert smoke.main() == 0
    output = capsys.readouterr()
    assert "portfolio checks passed" in output.out
    assert "ok    fmind (default)\n" in output.out
    assert "ok    fmind --json\n" in output.out
    assert "fmind whoami --json" in output.out
    assert "fmind --json whoami" in output.out
    assert "fmind read newer --raw" in output.out
    assert "ok    fmind news 2024-08-16 --json\n" in output.out
    assert not output.err
    mcp.assert_awaited_once()


@pytest.mark.parametrize("api_fails", [True, False])
def test_api_and_mcp_fail_independently(
    api_fails: bool, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[str] = []

    def portfolio() -> None:
        calls.append("API")
        if api_fails:
            raise RuntimeError("profile.metadata.name is missing")

    async def mcp() -> None:
        calls.append("MCP")
        if not api_fails:
            raise OSError("private transport diagnostic")

    monkeypatch.setattr(smoke, "smoke_portfolio", portfolio)
    monkeypatch.setattr(smoke, "smoke_mcp", mcp)
    assert smoke.main() == 1
    assert calls == ["API", "MCP"]
    error = capsys.readouterr().err
    assert ("FAIL  API" if api_fails else "FAIL  MCP") in error
    assert "private" not in error


@pytest.mark.usefixtures("remote")
def test_mcp_news_read_needs_a_published_edition(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(smoke, "load_news", lambda: {"editions": []})
    with pytest.raises(RuntimeError, match="no news edition for the MCP read check"):
        asyncio.run(smoke.smoke_mcp())


@pytest.mark.usefixtures("offline")
def test_portfolio_checks_need_a_published_edition(news_archive: dict[str, Any]) -> None:
    news_archive["editions"] = []
    with pytest.raises(RuntimeError, match="lists no news edition"):
        smoke.smoke_portfolio()


@pytest.mark.usefixtures("offline")
def test_portfolio_reports_failing_variant(monkeypatch: pytest.MonkeyPatch) -> None:
    original = smoke.CliRunner.invoke

    def fail_whoami(self: Any, cli_app: Any, args: list[str], **kwargs: Any) -> Any:
        if args == ["--no-color", "whoami"]:
            return original(self, cli_app, ["read", "absent"], **kwargs)
        return original(self, cli_app, args, **kwargs)

    monkeypatch.setattr(smoke.CliRunner, "invoke", fail_whoami)
    with pytest.raises(RuntimeError, match=r"1 portfolio check\(s\) failed"):
        smoke.smoke_portfolio()
