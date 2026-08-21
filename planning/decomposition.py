from __future__ import annotations

import asyncio

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from .models import Plan


PLANNER_SYSTEM = """You are a careful task-decomposition planner.

Produce a small executable DAG, not a prose checklist.
Every task must make a concrete contribution to the goal.
Independent research or analysis tasks should be parallel.
The plan must end with exactly one synthesis task depending on every necessary branch.


Return ONLY valid JSON.
Do NOT use Markdown.
Do NOT wrap the JSON in ```json or ``` blocks.

The JSON must have exactly this structure:
{
  "goal": "string",
  "tasks": [
    {
      "id": "string",
      "instruction": "string",
      "depends_on": ["string"],
      "tool": "string or null",
      "arguments": {}
    }
  ]
}
"""


class PlannedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    instruction: str
    depends_on: list[str]
    tool: str | None = None
    arguments: dict = Field(default_factory=dict)


class GeneratedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    tasks: list[PlannedTask]

async def decompose_goal(
    goal: str,
    llm: BaseChatModel,
    mcp=None,
) -> Plan:

    tool_text = ""

    if mcp is not None:
        tools = await mcp.list_tools()

        tool_text = "\n".join(
            f"""
TOOL: {tool.name}
DESCRIPTION: {tool.description or "No description"}
INPUT SCHEMA: {tool.input_schema}
"""
            for tool in tools.tools
        )

    generated = llm.with_structured_output(
        GeneratedPlan,
        method="json_mode",
    ).invoke(
        [
            ("system", PLANNER_SYSTEM),
            (
                "human",
                f"""
Decompose this goal into 3-6 tasks:

{goal!r}

Available MCP tools:
{tool_text}

Rules:
- Use ONLY tools from the available MCP tools list.
- Never invent a tool name.
- If a task does not require an MCP tool, use null.
- Use the exact tool name.
- Arguments must match the tool's input schema exactly.
- Use short task ids such as t1.
- Dependencies may refer only to tasks in the plan.
- Preserve the supplied goal exactly.

Return valid JSON only.
""",
            ),
        ],
        temperature=0.1,
    )

    payload = generated.model_dump()
    payload["goal"] = goal

    return Plan.model_validate(payload)


async def execute_plan(
    plan: Plan,
    llm: BaseChatModel,
    mcp=None,
    max_workers: int = 4,
) -> dict[str, str]:

    outputs: dict[str, str] = {}

    for batch in plan.execution_batches():

        async def execute_task(task_id: str):

            task = plan.task(task_id)

            context = "\n\n".join(
                f"OUTPUT FROM {dependency}:\n{outputs[dependency]}"
                for dependency in task.depends_on
            ) or "No prerequisite outputs."

            # -----------------------------------------
            # REAL MCP TOOL EXECUTION
            # -----------------------------------------

            if mcp is not None and task.tool:

                result = await mcp.call_tool(
                    task.tool,
                    task.arguments,
                )

                return task_id, "\n".join(result)

            # -----------------------------------------
            # LLM EXECUTION
            # -----------------------------------------

            prompt = f"""Overall goal: {plan.goal}

Current task: {task.instruction}

Prerequisite outputs:
{context}

Complete only the current task.
Be concrete and concise.
Use only the provided evidence.
Do not invent sources.
"""

            response = await asyncio.to_thread(
                llm.invoke,
                [
                    (
                        "system",
                        "You execute one node in a validated task DAG.",
                    ),
                    ("human", prompt),
                ],
            )

            content = response.content

            if not isinstance(content, str) or not content.strip():
                raise RuntimeError(
                    "The chat model returned an empty or unsupported response"
                )

            return task_id, content.strip()

        results = await asyncio.gather(
            *(execute_task(task_id) for task_id in batch)
        )

        for task_id, result in results:
            outputs[task_id] = result

    return outputs


def final_output(
    plan: Plan,
    outputs: dict[str, str],
) -> str:

    terminals = plan.terminal_tasks()

    if len(terminals) != 1:
        raise ValueError(
            f"Expected exactly one terminal synthesis task, found {terminals}"
        )

    return outputs[terminals[0]]