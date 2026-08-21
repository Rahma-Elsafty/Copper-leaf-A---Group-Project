from __future__ import annotations

from typing import Any

from mcp.client import ClientSession


class CopperleafMCPAdapter:
    """
    Thin adapter between the planning layer and the existing
    Copperleaf MCP client session.

    The planning algorithms use this adapter instead of accessing
    the database directly.
    """

    def __init__(self, session: ClientSession):
        self.session = session

    async def list_tools(self):
        """Return the tools exposed by the Copperleaf MCP server."""
        return await self.session.list_tools()

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        Call an existing Copperleaf MCP tool and return textual results.
        """

        result = await self.session.call_tool(
            tool_name,
            arguments or {},
        )

        texts: list[str] = []

        for item in result.content:
            if hasattr(item, "text"):
                texts.append(item.text)

        return texts

    async def read_resource(self, uri: str):
        """Read an existing Copperleaf MCP resource."""
        return await self.session.read_resource(uri)