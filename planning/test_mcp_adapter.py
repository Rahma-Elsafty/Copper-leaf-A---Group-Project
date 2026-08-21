import asyncio

from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)
from mcp.client import ClientSession

from planning.mcp_adapter import CopperleafMCPAdapter


async def main():

    server = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
    )

    async with stdio_client(server) as (
        read_stream,
        write_stream,
    ):

        async with ClientSession(
            read_stream,
            write_stream,
        ) as session:

            await session.initialize()

            mcp = CopperleafMCPAdapter(session)

            tools = await mcp.list_tools()

            print("Available tools:")

            for tool in tools.tools:
                print("-", tool.name)

            print("\nTesting real Copperleaf tools:")

            tests = [
                (
                    "list_low_stock_items",
                    {"location_id": 1},
                ),
                (
                    "get_location_budget",
                    {"location_id": 1},
                ),
                (
                    "get_staff",
                    {"staff_id": 2},
                ),
                (
                    "get_inventory_item",
                    {"stock_id": 1},
                ),
                (
                    "get_purchase_order",
                    {"po_id": 2},
                ),
            ]

            for tool_name, arguments in tests:

                print(f"\n--- {tool_name} ---")

                result = await mcp.call_tool(
                    tool_name,
                    arguments,
                )

                for item in result:
                    print(item)

if __name__ == "__main__":
    asyncio.run(main())