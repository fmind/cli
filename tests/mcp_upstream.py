"""Synthetic HTTP upstream for offline stdio subprocess tests."""

from __future__ import annotations

from unittest.mock import patch

import httpx2
from mcp.server import MCPServer


def upstream() -> MCPServer[None]:
    server: MCPServer[None] = MCPServer("Example", log_level="WARNING", instructions="Use the published example data.")

    @server.tool()
    def echo(value: str) -> str:
        """Return the supplied example text."""
        return value

    @server.resource("example://profile")
    def profile() -> str:
        return "Synthetic profile"

    @server.prompt()
    def brief(audience: str) -> str:
        return f"Brief for {audience}"

    return server


def main() -> None:
    from fmind import mcp
    from fmind.cli import app

    http_app = upstream().streamable_http_app(stateless_http=True, json_response=True)
    asgi = httpx2.ASGITransport(app=http_app)
    original = mcp.serve

    async def serve() -> None:
        async with http_app.router.lifespan_context(http_app):
            await original()

    async def handle(_transport: httpx2.AsyncHTTPTransport, request: httpx2.Request) -> httpx2.Response:
        return await asgi.handle_async_request(request)

    # Only the network hop is replaced: requests still pass through the bridge's
    # bounded transport, SDK serialization, and the upstream ASGI app.
    with (
        patch.object(httpx2.AsyncHTTPTransport, "handle_async_request", handle),
        patch.object(mcp, "serve", serve),
    ):
        app(["mcp"])


if __name__ == "__main__":
    main()
