"""Remote forwarding, failure, and subprocess stdio protocol contracts."""

import asyncio
import gzip
import json
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import httpx2
import mcp_types as types
import pytest
from mcp import Client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from typer.testing import CliRunner

from fmind import mcp
from fmind.api import origin_url
from fmind.cli import app
from tests.mcp_upstream import upstream


def _text(content: object) -> str:
    assert isinstance(content, types.TextContent | types.TextResourceContents)
    return content.text


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
            assert _text((await client.call_tool("echo", {"value": "example"})).content[0]) == "example"
            assert _text((await client.read_resource("example://profile")).contents[0]) == "Synthetic profile"
            prompt = await client.get_prompt("brief", {"audience": "testers"})
            assert _text(prompt.messages[0].content) == "Brief for testers"
            assert (await client.call_tool("missing", {})).is_error
            assert (await client.call_tool("echo", {})).is_error
            with pytest.raises(MCPError):
                await client.read_resource("example://missing")

        from mcp.server.lowlevel import Server

        async with (
            Client(Server("Empty"), cache=None) as empty_remote,
            Client(mcp.create_bridge(empty_remote), cache=None) as empty_client,
        ):
            assert empty_client.server_capabilities.tools is None
            assert empty_client.server_capabilities.resources is None
            assert empty_client.server_capabilities.prompts is None

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

        class Reset(httpx2.AsyncByteStream):
            async def __aiter__(self):
                yield b"abc"
                raise httpx2.ReadError("private diagnostic")

        monkeypatch.setattr(mcp, "MAX_BYTES", 5)
        deadline = asyncio.get_running_loop().time() + 1
        for chunks, message in ((Chunks(), "size limit"), (Reset(), "interrupted")):
            stream = mcp._BoundedStream(chunks, deadline)
            # A stream error is the one failure the SDK answers per request.
            with pytest.raises(httpx2.StreamError, match=message):
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
            if encoding == "identity":
                with pytest.raises(httpx2.StreamError, match="size limit"):
                    await client.get("https://example.test/mcp")
            else:
                assert (await client.get("https://example.test/mcp")).status_code == 502
        assert response.is_closed

        class SyncOnly(httpx2.SyncByteStream):
            pass

        invalid = httpx2.Response(200, stream=SyncOnly())
        monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", AsyncMock(return_value=invalid))
        async with httpx2.AsyncClient(transport=mcp._BoundedTransport()) as client:
            with pytest.raises(mcp.FmindError, match="invalid stream"):
                await client.get("https://example.test/mcp")

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
                assert (await client.get("https://example.test/mcp")).status_code == 504
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

    asyncio.run(run())
    assert stopped.is_set()


@pytest.mark.parametrize("failure", ["size", "encoding", "connect", "reset"])
def test_one_failed_exchange_leaves_the_bridge_serving(monkeypatch: pytest.MonkeyPatch, failure: str) -> None:
    class Body(httpx2.AsyncByteStream):
        """A network-like body: unlike `content=`, httpx2 has not read it in advance."""

        def __init__(self, data: bytes, *, reset: bool = False) -> None:
            self.data = data
            self.reset = reset

        async def __aiter__(self):
            yield self.data
            if self.reset:
                raise httpx2.ReadError("private diagnostic")

    http_app = upstream().streamable_http_app(stateless_http=True, json_response=True)
    asgi = httpx2.ASGITransport(app=http_app)
    broken = False

    async def handle(_transport: object, request: httpx2.Request) -> httpx2.Response:
        # Only the network hop is replaced; the bridge's own bounds still run.
        if broken and failure == "connect":
            raise httpx2.ConnectError("private diagnostic", request=request)
        response = await asgi.handle_async_request(request)
        if not broken:
            return response
        body = await response.aread()
        json_type = {"content-type": "application/json"}
        if failure == "size":
            # Valid JSON-RPC with trailing whitespace, past the bound set below.
            return httpx2.Response(200, headers=json_type, stream=Body(body + b" " * 2048), request=request)
        if failure == "encoding":
            headers = {**json_type, "content-encoding": "gzip"}
            return httpx2.Response(200, headers=headers, stream=Body(gzip.compress(body)), request=request)
        return httpx2.Response(200, headers=json_type, stream=Body(body[:10], reset=True), request=request)

    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", handle)

    async def run() -> None:
        nonlocal broken
        async with (
            http_app.router.lifespan_context(http_app),
            httpx2.AsyncClient(transport=mcp._BoundedTransport()) as http,
            Client(streamable_http_client("http://127.0.0.1:8000/mcp", http_client=http), cache=None) as remote,
            Client(mcp.create_bridge(remote), cache=None) as client,
        ):
            monkeypatch.setattr(mcp, "MAX_BYTES", 1024)
            broken = True
            with pytest.raises(MCPError) as caught:
                await client.call_tool("echo", {"value": "lost"})
            assert "private" not in str(caught.value)
            broken = False
            assert _text((await client.call_tool("echo", {"value": "served"})).content[0]) == "served"

    asyncio.run(run())


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
                assert _text((await client.call_tool("echo", {"value": "stdio"})).content[0]) == "stdio"
                assert _text((await client.read_resource("example://profile")).contents[0]) == "Synthetic profile"
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


def test_failure_after_connecting_does_not_blame_the_remote(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def connected(*args: object, **kwargs: object) -> AsyncGenerator[tuple[None, None]]:
        yield None, None

    class Bridge:
        def create_initialization_options(self) -> None:
            return None

        async def run(self, *args: object) -> None:
            # What the SDK's stdio writer raises once the host closes stdout.
            raise BrokenPipeError(32, "Broken pipe")

    monkeypatch.setattr(mcp, "Client", connected)
    monkeypatch.setattr(mcp, "stdio_server", connected)
    monkeypatch.setattr(mcp, "create_bridge", lambda remote: Bridge())
    result = CliRunner().invoke(app, ["mcp"])
    assert result.exit_code == 1
    assert result.stdout == ""
    assert result.stderr == "fmind: the MCP bridge stopped unexpectedly after connecting\n"


def test_missing_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "fmind.mcp", None)
    result = CliRunner().invoke(app, ["mcp"])
    assert result.exit_code == 1
    assert "uv tool install --upgrade 'fmind[mcp]'" in result.stderr
    assert not result.stdout


def test_json_is_rejected() -> None:
    assert CliRunner().invoke(app, ["--json", "mcp"]).exit_code == 2
