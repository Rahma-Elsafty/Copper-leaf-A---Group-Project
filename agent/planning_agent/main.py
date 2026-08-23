"""
agent/planning_agent/main.py — entry point for the restocking planning agent.

THIS is the file you run. `planning/` is a library (decompose_goal,
execute_plan, ...) — it has no `if __name__ == "__main__"` of its own on
purpose, exactly like `mcp_server/tools_read.py` isn't run directly either.
This file plays the same role for the planning agent that
`agent/memory_rag_agent/client.py` plays for the memory/RAG agent: it opens
the MCP session, builds the LLM, and calls into the library.

Run it (from the repo root, same way you'd run the existing agent):
    python -m agent.planning_agent.main

Requires (same as the rest of the repo):
    pip install -r requirements.txt
    a .env with your LLM provider's API key (MISTRAL_API_KEY, OPENAI_API_KEY, ...)
    mcp_server/ runnable as `python -m mcp_server.server` (it already is)

Right now this runs the FULL pipeline end-to-end against your REAL MCP
server and REAL database: decomposition-first, dynamic decomposition, and
every sub-task routed through Router (PS/ToT/LATS, LATS grounded by the
real place_purchase_order response).
"""
from __future__ import annotations

import asyncio

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# TODO(team): swap for whatever provider you actually use elsewhere in the
# repo (this matches the toolkit's original default). planning/ itself never
# imports a concrete provider — only this file needs to know which one.
from langchain_mistralai import ChatMistralAI

from planning import RestockEnvironment, Router, decompose_goal, dynamic_decomposition, execute_plan, final_output


class PlanningMCPClient:
    """Satisfies the MCPClient protocol in planning/decomposition.py.
    Thin wrapper around a live mcp ClientSession — same shape as
    CopperleafAgent.call_mcp_tool in agent/memory_rag_agent/client.py, so if
    you'd rather reuse that agent's own session instead of opening a second
    one, you can hand its `call_mcp_tool` method here directly and delete
    this class."""

    def __init__(self, session: ClientSession):
        self.session = session

    async def call_mcp_tool(self, tool_name: str, arguments: dict) -> str:
        result = await self.session.call_tool(tool_name, arguments)
        texts = [item.text for item in result.content if hasattr(item, "text")]
        return "\n".join(texts)


async def run_decomposition_first(mcp_client: PlanningMCPClient, llm, router: Router) -> None:
    goal = "Restock Downtown Kitchen's low-stock ingredients within this month's budget"
    context_facts = {"location_id": 1, "requested_by": 2}  # James Whitfield, kitchen_manager @ Downtown

    plan = decompose_goal(goal, llm, context_facts)
    print("\n=== DECOMPOSITION-FIRST PLAN ===")
    print(plan.model_dump_json(indent=2))
    print("\nExecution batches:", plan.execution_batches())

    outputs = await execute_plan(plan, mcp_client, executor=router.route)
    print("\n=== OUTPUTS ===")
    for task_id, output in outputs.items():
        print(f"[{task_id}] {output}")

    print("\n=== FINAL (decomposition-first) ===")
    print(final_output(plan, outputs))


async def run_dynamic(mcp_client: PlanningMCPClient, llm, router: Router) -> None:
    goal = "Restock Downtown Kitchen's low-stock ingredients within this month's budget"
    context_facts = {"location_id": 1, "requested_by": 2}

    history = await dynamic_decomposition(goal, llm, mcp_client, context_facts, executor=router.route)
    print("\n=== DYNAMIC DECOMPOSITION TRACE ===")
    for step_text, result in history:
        print(f"- {step_text}\n  -> {result}\n")


async def main() -> None:
    load_dotenv()

    server = StdioServerParameters(command="python", args=["-m", "mcp_server.server"])
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            mcp_client = PlanningMCPClient(session)

            llm = ChatMistralAI(model="mistral-small-latest", random_seed=42, max_retries=2)
            environment = RestockEnvironment(mcp_client, requested_by=2)
            router = Router(llm, environment)

            await run_decomposition_first(mcp_client, llm, router)
            await run_dynamic(mcp_client, llm, router)


if __name__ == "__main__":
    asyncio.run(main())
