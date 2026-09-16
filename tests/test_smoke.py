"""Offline regressions for the live compatibility checker itself."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from tests import smoke


def test_mcp_checks_article_and_calculator_with_live_inputs(monkeypatch: pytest.MonkeyPatch) -> None:
    client = AsyncMock()
    names = ["get_profile", "search_articles", "get_article", "compare_llm_hosting"]
    client.list_tools.return_value = SimpleNamespace(
        tools=[SimpleNamespace(name=name, annotations=SimpleNamespace(read_only_hint=True)) for name in names]
    )
    client.list_resources.return_value = SimpleNamespace(
        resources=[SimpleNamespace(name="example", uri="example://resource")]
    )
    client.list_prompts.return_value = SimpleNamespace(prompts=[SimpleNamespace(name="brief", arguments=[])])
    client.call_tool.return_value = SimpleNamespace(is_error=False, content=["result"])
    client.read_resource.return_value = SimpleNamespace(contents=["resource"])
    client.get_prompt.return_value = SimpleNamespace(messages=["prompt"])
    client.__aenter__.return_value = client
    monkeypatch.setattr(smoke, "Client", lambda *args, **kwargs: client)
    monkeypatch.setattr(smoke, "load_profile", lambda: {"articles": [{"slug": "fresh-article"}]})

    asyncio.run(smoke.smoke_mcp())

    assert [call.args for call in client.call_tool.await_args_list] == [
        ("get_profile", {}),
        ("search_articles", {"query": "compatibility", "limit": 1}),
        ("get_article", {"slug": "fresh-article"}),
        ("compare_llm_hosting", {"parameters": {}}),
    ]


def test_checks_every_portfolio_variant(
    offline: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    mcp = AsyncMock()
    monkeypatch.setattr(smoke, "smoke_mcp", mcp)
    assert smoke.main() == 0
    output = capsys.readouterr()
    assert "portfolio checks passed" in output.out
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
