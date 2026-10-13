"""Remote forwarding, failure, and subprocess stdio protocol contracts."""

from __future__ import annotations

import asyncio
import json
import sys
from unittest.mock import AsyncMock

import httpx2
import mcp_types as types
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from typer.testing import CliRunner

from fmind import mcp
from fmind.api import FmindError, origin_url
from fmind.cli import app
from tests.mcp_upstream import upstream


def test_endpoint_follows_profile_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    assert origin_url("/mcp") == "https://www.fmind.dev/mcp"
    monkeypatch.setenv("FMIND_PROFILE_URL", "http://127.0.0.1:8123/custom/profile?ignored=yes")
    assert origin_url("/mcp") == "http://127.0.0.1:8123/mcp"


def test_forwarding() -> None:
    async def run() -> None:
        async with (
            Client(upstream(), cache=None) as remote,
            Client(mcp.create_bridge(remote), cache=None) as client,
        ):
            assert client.instructions == remote.instructions
            assert (await client.list_tools()).tools == (await remote.list_tools()).tools
            assert (await client.list_resources()).resources == (await remote.list_resources()).resources
            assert (await client.list_prompts()).prompts == (await remote.list_prompts()).prompts
            assert not (await client.list_resource_templates()).resource_templates
            assert (await client.call_tool("echo", {"value": "example"})).content[0].text == "example"
            assert (await client.read_resource("example://profile")).contents[0].text == "Synthetic profile"
            assert (await client.get_prompt("brief", {"audience": "testers"})).messages[
                0
            ].content.text == "Brief for testers"
            assert (await client.call_tool("missing", {})).is_error
            assert (await client.call_tool("echo", {})).is_error
            with pytest.raises(MCPError):
                await client.read_resource("example://missing")

    asyncio.run(run())


def test_cursor_errors_and_cache_hints(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        async with Client(upstream(), cache=None) as remote:
            send = AsyncMock(return_value=types.ListToolsResult(tools=[], next_cursor="next", ttl_ms=1000))
            monkeypatch.setattr(remote.session, "send_request", send)
            async with Client(mcp.create_bridge(remote)) as client:
                for _ in range(2):
                    result = await client.list_tools(cursor="page-two")
                    assert result.next_cursor == "next"
                    assert result.ttl_ms == 0
                assert send.await_count == 2
                assert send.call_args.args[0].params.cursor == "page-two"
                send.side_effect = MCPError(types.INVALID_PARAMS, "invalid example arguments")
                with pytest.raises(MCPError, match="invalid example arguments"):
                    await client.list_tools()
                send.side_effect = OSError("private diagnostic")
                with pytest.raises(MCPError, match="could not read the remote MCP server") as caught:
                    await client.list_tools()
                assert "private diagnostic" not in str(caught.value)

    asyncio.run(run())


def test_timeout_and_cancellation(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        stopped = asyncio.Event()

        async def stall(*args: object, **kwargs: object) -> None:
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        async with Client(upstream(), cache=None) as remote:
            monkeypatch.setattr(remote.session, "send_request", stall)
            async with Client(mcp.create_bridge(remote), cache=None) as client:
                monkeypatch.setattr(mcp, "TIMEOUT_SECONDS", 0.02)
                with pytest.raises(MCPError, match="could not read"):
                    await client.list_tools()
                assert stopped.is_set()
                stopped.clear()
                monkeypatch.setattr(mcp, "TIMEOUT_SECONDS", 15)
                task = asyncio.create_task(client.list_tools())
                await asyncio.sleep(0.01)
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                await asyncio.wait_for(stopped.wait(), 1)

    asyncio.run(run())


def test_response_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        class Chunks(httpx2.AsyncByteStream):
            async def __aiter__(self):
                yield b"abc"
                yield b"def"

        monkeypatch.setattr(mcp, "MAX_BYTES", 5)
        stream = mcp._BoundedStream(Chunks(), asyncio.get_running_loop().time() + 1)
        with pytest.raises(FmindError, match="size limit"):
            _ = [part async for part in stream]
        await stream.aclose()

    asyncio.run(run())


@pytest.mark.parametrize("encoding", ["identity", "gzip"])
def test_http_transport_bound(monkeypatch: pytest.MonkeyPatch, encoding: str) -> None:
    async def run() -> None:
        class Chunks(httpx2.AsyncByteStream):
            async def __aiter__(self):
                yield b"abc"
                yield b"def"

        response = httpx2.Response(200, headers={"content-encoding": encoding}, stream=Chunks())
        monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", AsyncMock(return_value=response))
        monkeypatch.setattr(mcp, "MAX_BYTES", 5)
        async with httpx2.AsyncClient(transport=mcp._BoundedTransport()) as client:
            with pytest.raises(FmindError, match=r"size limit|uncompressed"):
                await client.get("https://example.test/mcp")
        assert response.is_closed

    asyncio.run(run())


def test_http_headers_have_a_total_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    async def run() -> None:
        stopped = asyncio.Event()

        async def stalled(*args: object) -> None:
            try:
                await asyncio.Event().wait()
            finally:
                stopped.set()

        monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", stalled)
        monkeypatch.setattr(mcp, "TIMEOUT_SECONDS", 0.02)
        async with httpx2.AsyncClient(transport=mcp._BoundedTransport()) as client:
            async with asyncio.timeout(1):
                with pytest.raises(httpx2.ReadTimeout):
                    await client.get("https://example.test/mcp")
                assert stopped.is_set()

    asyncio.run(run())


def test_legacy_http_body_stops_after_request_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped = asyncio.Event()

    async def run() -> None:
        class Endless(httpx2.AsyncByteStream):
            async def __aiter__(self):
                while True:
                    yield b" "
                    await asyncio.sleep(0.005)

            async def aclose(self) -> None:
                stopped.set()

        async def handle(_transport: object, request: httpx2.Request) -> httpx2.Response:
            body = json.loads(request.content)
            if body["method"] == "initialize":
                return httpx2.Response(
                    200,
                    json={
                        "jsonrpc": "2.0",
                        "id": body["id"],
                        "result": {
                            "protocolVersion": "2025-11-25",
                            "capabilities": {"tools": {}},
                            "serverInfo": {"name": "example", "version": "1"},
                        },
                    },
                )
            if body["method"].startswith("notifications/"):
                return httpx2.Response(202)
            return httpx2.Response(200, headers={"content-type": "application/json"}, stream=Endless())

        monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", handle)
        monkeypatch.setattr(mcp, "TIMEOUT_SECONDS", 0.03)
        async with (
            httpx2.AsyncClient(transport=mcp._BoundedTransport()) as http,
            Client(
                streamable_http_client("https://example.test/mcp", http_client=http),
                mode="legacy",
                cache=None,
                read_timeout_seconds=1,
            ) as remote,
            Client(mcp.create_bridge(remote), cache=None) as client,
        ):
            with pytest.raises(MCPError):
                await client.list_tools()
            # The caller timing out must not leave a slow response running until
            # bridge shutdown, even when a legacy server ignores cancellation.
            await asyncio.wait_for(stopped.wait(), 0.5)

    # The SDK may close its task group when the legacy POST fails. Its transport
    # timeout is expected; the test's wait_for TimeoutError must still fail.
    try:
        asyncio.run(run())
    except* httpx2.ReadTimeout:
        pass
    assert stopped.is_set()


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_stdio_subprocess(mode: str, tmp_path) -> None:
    async def run() -> None:
        with (tmp_path / "stderr").open("w+") as errors:
            params = StdioServerParameters(
                command=sys.executable,
                args=["-W", "error", "-m", "tests.mcp_upstream"],
                env={"FMIND_PROFILE_URL": "http://127.0.0.1:8000/api/profile"},
            )
            from mcp.client.stdio import stdio_client

            async with Client(stdio_client(params, errlog=errors), mode=mode, cache=None) as client:
                assert [tool.name for tool in (await client.list_tools()).tools] == ["echo"]
                assert (await client.call_tool("echo", {"value": "stdio"})).content[0].text == "stdio"
                assert (await client.read_resource("example://profile")).contents[0].text == "Synthetic profile"
                assert (await client.get_prompt("brief", {"audience": "hosts"})).messages
            errors.seek(0)
            assert errors.read() == ""

    asyncio.run(run())


def test_startup_failure_is_one_line(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FMIND_PROFILE_URL", "invalid")
    result = CliRunner().invoke(app, ["mcp"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr.startswith("fmind: FMIND_PROFILE_URL")
    assert len(result.stderr.splitlines()) == 1


def test_connection_failure_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("private diagnostic")

    monkeypatch.setattr(mcp, "_BoundedTransport", lambda: httpx2.MockTransport(fail))
    result = CliRunner().invoke(app, ["mcp"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert (
        result.stderr
        == "fmind: could not connect to the remote MCP server; check your connection and FMIND_PROFILE_URL\n"
    )


def test_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fmind.mcp", None)
    result = CliRunner().invoke(app, ["mcp"])
    assert result.exit_code == 1
    assert "uv tool install --upgrade 'fmind[mcp]'" in result.stderr
    assert not result.stdout


def test_json_is_rejected() -> None:
    assert CliRunner().invoke(app, ["--json", "mcp"]).exit_code == 2
