"""Offline regressions for the live compatibility checker itself."""

from unittest.mock import AsyncMock

import pytest

from tests import smoke


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
