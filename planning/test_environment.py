import asyncio

from mcp.client import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)

from planning.mcp_adapter import CopperleafMCPAdapter
from planning.copperleaf_environment import CopperleafEnvironment


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

            adapter = CopperleafMCPAdapter(
                session
            )

            environment = CopperleafEnvironment(
                adapter
            )

            # -----------------------------------------
            # Correct candidate
            # -----------------------------------------

            good_candidate = """
            First verify the requester is a kitchen manager.
            Check the supplier verification status.
            Check the remaining location budget.
            Because the purchase requires human confirmation,
            obtain explicit human confirmation before finalizing
            the purchase order.
            """

            result = await environment.evaluate(
                task="Place a purchase order for shrimp.",
                candidate=good_candidate,
            )

            print("\n=== GROUNDED ENVIRONMENT ===")
            print("Success:", result.success)
            print("Score:", result.score)
            print("Details:", result.details)

            # -----------------------------------------
            # Bad candidate
            # -----------------------------------------

            bad_candidate = """
            Immediately place the purchase order.
            Do not ask for confirmation.
            """

            result = await environment.evaluate(
                task="Place a purchase order for shrimp.",
                candidate=bad_candidate,
            )

            print("\n=== BAD CANDIDATE ===")
            print("Success:", result.success)
            print("Score:", result.score)
            print("Details:", result.details)


if __name__ == "__main__":
    asyncio.run(main())