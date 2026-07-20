"""
Wraps a single MCP server connection for the lifetime of the app.

Today this connects over stdio to a locally-spawned example server
(example_mcp_server.py). To point this at a *remote* MCP server instead,
swap `stdio_client(...)` below for the SDK's streamable-HTTP/SSE client
(see https://modelcontextprotocol.io/docs/sdk) — none of the FastAPI route
code needs to change, only this file.

To connect to MULTIPLE MCP servers, keep a dict of named ClientSessions
here instead of a single `self.session`, and pick one per request.
"""

from contextlib import AsyncExitStack

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from app.config import settings


class MCPClientManager:
    def __init__(self) -> None:
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None

    async def connect(self) -> None:
        params = StdioServerParameters(
            command=settings.mcp_server_command,
            args=settings.mcp_server_args_list,
            env={"DATABASE_URL": settings.database_url},
        )
        read_stream, write_stream = await self._stack.enter_async_context(stdio_client(params))
        self.session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()

    async def disconnect(self) -> None:
        await self._stack.aclose()
        self.session = None

    async def list_tools(self) -> list[dict]:
        assert self.session is not None, "MCP session not connected"
        result = await self.session.list_tools()
        return [tool.model_dump() for tool in result.tools]

    async def call_tool(self, name: str, arguments: dict):
        assert self.session is not None, "MCP session not connected"
        result = await self.session.call_tool(name, arguments)
        return [content.model_dump() for content in result.content]


mcp_manager = MCPClientManager()
