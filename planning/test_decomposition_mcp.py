from __future__ import annotations

import asyncio

from mcp.client import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)

from planning.mcp_adapter import CopperleafMCPAdapter
from planning.decomposition import (
    decompose_goal,
    execute_plan,
    final_output,
)

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
load_dotenv()

llm = ChatOpenAI(
    model=os.getenv(
        "COPPERLEAF_LLM_MODEL",
        "openai/gpt-oss-20b:free",
    ),
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
    temperature=0.1,
)

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

            print("\n===================================")
            print(" Copperleaf Decomposition-First")
            print("===================================\n")

            await session.initialize()

            print("MCP connected.\n")

            # -----------------------------------------
            # Adapter
            # -----------------------------------------

            mcp = CopperleafMCPAdapter(session)

         

            # -----------------------------------------
            # REAL COPPERLEAF GOAL
            # -----------------------------------------

            goal = (
                "Check Downtown Kitchen inventory and budget "
                "to determine whether a purchase may be needed."
            )

            print("GOAL:")
            print(goal)

            # -----------------------------------------
            # DECOMPOSITION
            # -----------------------------------------

            print("\nGenerating plan...\n")

            plan = await decompose_goal(
                    goal,
                    llm,
                    mcp,
                )

            print("=== GENERATED PLAN ===")

            print(f"\nGoal: {plan.goal}\n")

            for task in plan.tasks:

                print(f"Task: {task.id}")
                print(f"  Instruction: {task.instruction}")
                print(f"  Depends on: {task.depends_on}")
                print(f"  MCP tool: {task.tool}")
                print(f"  Arguments: {task.arguments}")
                print()

            print("Execution batches:")
            print(plan.execution_batches())

            # -----------------------------------------
            # EXECUTE
            # -----------------------------------------

            print("\n=== EXECUTION ===\n")

            outputs = await execute_plan(
                plan=plan,
                llm=llm,
                mcp=mcp,
            )

            for task_id, output in outputs.items():

                print(f"\n--- {task_id} ---")
                print(output)

            # -----------------------------------------
            # FINAL OUTPUT
            # -----------------------------------------

            print("\n=== FINAL OUTPUT ===\n")

            result = final_output(
                plan,
                outputs,
            )

            print(result)


if __name__ == "__main__":
    asyncio.run(main())