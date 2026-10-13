"""Offline regressions for the live compatibility checker itself."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests import smoke


@pytest.fixture
def remote(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    client = AsyncMock()
    names = ["get_profile", "search_articles", "get_article", "compare_llm_hosting", "compare_mcp_context_cost"]
    client.list_tools.return_value = SimpleNamespace(
        tools=[SimpleNamespace(name=name, annotations=SimpleNamespace(read_only_hint=True)) for name in names],
        next_cursor=None,
    )
    client.list_resources.return_value = SimpleNamespace(
        resources=[SimpleNamespace(name="example", uri="example://resource")], next_cursor=None
    )
    client.list_prompts.return_value = SimpleNamespace(
        prompts=[SimpleNamespace(name="brief", arguments=[])], next_cursor=None
    )
    client.list_resource_templates.return_value = SimpleNamespace(resource_templates=[], next_cursor=None)
    client.call_tool.return_value = SimpleNamespace(is_error=False, content=["result"])
    client.read_resource.return_value = SimpleNamespace(contents=["resource"])
    client.get_prompt.return_value = SimpleNamespace(messages=["prompt"])
    client.__aenter__.return_value = client
    monkeypatch.setattr(smoke, "Client", lambda *args, **kwargs: client)
    monkeypatch.setattr(smoke, "load_profile", lambda: {"articles": [{"slug": "fresh-article"}]})
    return client


def test_mcp_checks_article_and_calculator_with_live_inputs(remote: AsyncMock) -> None:

    asyncio.run(smoke.smoke_mcp())

    assert [call.args for call in remote.call_tool.await_args_list] == [
        ("get_profile", {}),
        ("search_articles", {"query": "compatibility", "limit": 1}),
        ("get_article", {"slug": "fresh-article"}),
        ("compare_llm_hosting", {"parameters": {}}),
        ("compare_mcp_context_cost", {"parameters": {}}),
    ]


@pytest.mark.parametrize("field", ["tools", "resources", "prompts", "resource_templates"])
def test_mcp_checks_later_catalog_pages(remote: AsyncMock, field: str) -> None:
    listing = getattr(remote, f"list_{field}")
    first = listing.return_value
    first.next_cursor = "page-two"
    listing.side_effect = [first, RuntimeError("second page failed")]
    with pytest.raises(RuntimeError, match="second page failed"):
        asyncio.run(smoke.smoke_mcp())
    assert [call.kwargs for call in listing.await_args_list] == [{"cursor": None}, {"cursor": "page-two"}]


def test_mcp_exercises_entries_on_later_pages(remote: AsyncMock) -> None:
    first = remote.list_tools.return_value
    first.next_cursor = "page-two"
    remote.list_tools.side_effect = [
        first,
        SimpleNamespace(
            tools=[SimpleNamespace(name="later-tool", annotations=SimpleNamespace(read_only_hint=True))],
            next_cursor=None,
        ),
    ]
    asyncio.run(smoke.smoke_mcp())
    remote.call_tool.assert_any_await("later-tool", {})


def test_mcp_rejects_repeated_pagination_cursors(remote: AsyncMock) -> None:
    remote.list_tools.return_value.next_cursor = "repeated"
    with pytest.raises(RuntimeError, match="repeated a pagination cursor"):
        asyncio.run(smoke.smoke_mcp())
    assert remote.list_tools.await_count == 2


def test_checks_every_portfolio_variant(
    offline: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
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
