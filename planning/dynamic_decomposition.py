"""
planning/dynamic_decomposition.py — interleaved (dynamic) decomposition for
the Copperleaf Kitchen restocking agent.

Forked from algorithms/dynamic_decomposition.py. Owned by Person 1.

This is where decomposition-first is expected to diverge for real: it plans
the WHOLE restock order upfront, so if the first purchase order comes back
`requires_confirmation` (over 80% of remaining budget, or an unverified
supplier — see mcp_server/tools_write.py::place_purchase_order),
decomposition-first has already committed to ordering the rest and will
blindly keep going. Dynamic decomposition sees that real result before
deciding the next ingredient/supplier, and can react (pick a cheaper
supplier, skip an item, surface the confirmation first) instead of
overspending the location's budget. That divergence — not a synthetic one —
is the comparison case the assignment asks for.
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict

from .dag import Task, TaskKind
from .decomposition import DEFAULT_TOOL_CATALOG, MCPClient, TaskExecutor, stub_executor


class DynamicDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    done: bool
    next_task: str
    kind: TaskKind = "ps"
    tool_name: str | None = None
    tool_args: dict | None = None


async def dynamic_decomposition(
    goal: str,
    llm: BaseChatModel,
    mcp_client: MCPClient,
    context_facts: dict,
    executor: TaskExecutor = stub_executor,
    tool_catalog: str = DEFAULT_TOOL_CATALOG,
    max_steps: int = 8,
) -> list[tuple[str, str]]:
    facts_text = "\n".join(f"- {key}: {value}" for key, value in context_facts.items()) or "- None given."
    history: list[tuple[str, str]] = []
    for step in range(max_steps):
        observation = "\n".join(f"{task}: {result}" for task, result in history) or "None"
        decision = llm.with_structured_output(
            DynamicDecision,
            method="json_schema",
        ).invoke([
            ("system", f"""You are the adaptive restocking planner for Copperleaf Kitchen.
Use prior observations before deciding what comes next — if the last purchase
order needed confirmation or was rejected, that must change your next step,
not be ignored.

Known facts, use exactly as given:
{facts_text}

Prefer "deterministic" (a direct MCP tool call) whenever one of these tools
alone resolves the next step:
{tool_catalog}
Otherwise use "reasoning" or "retrieval" per the shared task-kind contract."""),
            ("human", f"""Goal: {goal}
Completed work and observations:
{observation}

Decide the single best next task. Set done to true only when every low-stock
ingredient has been addressed. When done is true, use an empty string for
next_task."""),
        ], temperature=0.1)
        if decision.done:
            break
        task_text = decision.next_task.strip()
        if not task_text:
            raise ValueError(f"Dynamic planner omitted next_task at step {step + 1}")

        if decision.kind == "deterministic":
            if not decision.tool_name:
                raise ValueError(f"Step {step + 1} is 'deterministic' but named no tool")
            result = await mcp_client.call_mcp_tool(decision.tool_name, decision.tool_args or {})
        else:
            step_task = Task(id=f"step{step + 1}", instruction=task_text, kind=decision.kind)
            result = await executor(step_task, None, observation)

        if not isinstance(result, str) or not result.strip():
            raise RuntimeError("A dynamic step returned an empty or unsupported result")
        history.append((task_text, result.strip()))
    return history
