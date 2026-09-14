"""Bridge the website's read-only MCP surface from Streamable HTTP to stdio."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Any

import httpx2
import mcp_types as types
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.server.context import ServerRequestContext
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import MCPError

from fmind import __version__
from fmind.api import MAX_BYTES, TIMEOUT_SECONDS, USER_AGENT, FmindError, origin_url


class _BoundedStream(httpx2.AsyncByteStream):
    def __init__(self, stream: httpx2.AsyncByteStream) -> None:
        self.stream = stream

    async def __aiter__(self) -> AsyncIterator[bytes]:
        size = 0
        async for chunk in self.stream:
            size += len(chunk)
            if size > MAX_BYTES:
                raise FmindError("the remote MCP response exceeded the size limit")
            yield chunk

    async def aclose(self) -> None:
        await self.stream.aclose()


class _BoundedTransport(httpx2.AsyncHTTPTransport):
    async def handle_async_request(self, request: httpx2.Request) -> httpx2.Response:
        response = await super().handle_async_request(request)
        if response.headers.get("content-encoding", "identity") != "identity":
            await response.aclose()
            raise FmindError("the remote MCP server ignored the uncompressed response requirement")
        if not isinstance(response.stream, httpx2.AsyncByteStream):
            raise FmindError("the remote MCP transport returned an invalid stream")
        response.stream = _BoundedStream(response.stream)
        return response


def create_bridge(remote: Client) -> Server[Any]:
    """Forward protocol operations without copying portfolio tools or schemas."""
    server: Server[Any] = Server("fmind", version=__version__, instructions=remote.instructions)

    def register(method: str, params_type: type[types.RequestParams], result_type: type[types.Result]) -> None:
        async def forward(_ctx: ServerRequestContext[Any], params: types.RequestParams) -> types.Result:
            try:
                async with asyncio.timeout(TIMEOUT_SECONDS):
                    result = await remote.session.send_request(types.Request(method=method, params=params), result_type)
                # Strip upstream cache hints: every bridge request must reach the website.
                payload = result.model_dump(by_alias=True, mode="json", exclude_none=True)
                payload.pop("ttlMs", None)
                payload.pop("cacheScope", None)
                return result_type.model_validate(payload)
            except MCPError:
                raise
            except Exception as error:
                raise MCPError(
                    types.INTERNAL_ERROR,
                    "could not read the remote MCP server; check your connection and FMIND_PROFILE_URL",
                ) from error

        server.add_request_handler(method, params_type, forward)

    capabilities = remote.server_capabilities
    if capabilities.tools is not None:
        register("tools/list", types.PaginatedRequestParams, types.ListToolsResult)
        register("tools/call", types.CallToolRequestParams, types.CallToolResult)
    if capabilities.resources is not None:
        register("resources/list", types.PaginatedRequestParams, types.ListResourcesResult)
        register("resources/templates/list", types.PaginatedRequestParams, types.ListResourceTemplatesResult)
        register("resources/read", types.ReadResourceRequestParams, types.ReadResourceResult)
    if capabilities.prompts is not None:
        register("prompts/list", types.PaginatedRequestParams, types.ListPromptsResult)
        register("prompts/get", types.GetPromptRequestParams, types.GetPromptResult)
    return server


async def serve() -> None:
    """Connect once and serve until stdin closes; cancellation closes remote I/O."""
    endpoint = origin_url("/mcp")
    # Protocol failures carry safe messages; SDK HTTP diagnostics can contain URLs.
    logging.getLogger("mcp").setLevel(logging.CRITICAL)
    try:
        async with (
            httpx2.AsyncClient(
                transport=_BoundedTransport(),
                timeout=TIMEOUT_SECONDS,
                headers={"User-Agent": USER_AGENT, "Cache-Control": "no-cache", "Accept-Encoding": "identity"},
            ) as http,
            Client(
                streamable_http_client(endpoint, http_client=http),
                read_timeout_seconds=TIMEOUT_SECONDS,
                cache=None,
            ) as remote,
            stdio_server() as (reader, writer),
        ):
            server = create_bridge(remote)
            await server.run(reader, writer, server.create_initialization_options())
    except Exception as error:
        message = "could not connect to the remote MCP server; check your connection and FMIND_PROFILE_URL"
        raise FmindError(message) from error
