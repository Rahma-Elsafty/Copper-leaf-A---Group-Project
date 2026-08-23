"""
planning/decomposition.py — decomposition-first DAG planning & execution
for Copperleaf Kitchen's restocking agent.

Forked from algorithms/decomposition.py (AmrSheta22/task_decomposition_and_planning).
Owned by Person 1.

REAL PROBLEM THIS DAG SOLVES (working assumption — confirm/rename in README):
  "Restock every ingredient at a location that has fallen at/under its
  reorder_threshold, deciding a supplier and quantity per ingredient inside
  the location's remaining monthly budget, while some suppliers are
  unverified and some orders will need human confirmation (already enforced
  server-side — see mcp_server/tools_write.py::place_purchase_order)."

Why this needs a DAG and not one call: several ingredients can be low at
once, each with its own candidate suppliers/prices, and committing to a full
order plan before seeing whether the FIRST order actually clears budget or
supplier-verification is exactly the failure mode dynamic_decomposition.py
(this package) is built to catch — see that module's docstring.

What changed vs. the toolkit:
  1. Real MCP tool catalog + task `kind` routing (dag.py's TaskKind):
       - "deterministic" tasks call our real, already-built MCP tools
         directly (list_low_stock_items, list_suppliers, get_supplier,
         place_purchase_order) via `mcp_client.call_mcp_tool(...)` — the
         SAME method name/signature as `CopperleafAgent.call_mcp_tool` in
         the memory/RAG agent's client.py, so this module can be driven by
         the existing agent's live MCP session instead of a second one.
       - "reasoning" tasks (e.g. deciding restock priority across several
         low-stock ingredients) route to Person 2's PS/ToT.
       - "retrieval" tasks (placing the actual purchase orders, where
         success/failure is a real server fact, not model opinion) route to
         Person 2's LATS, grounded by Person 3's environment.py.
  2. `mcp_client.call_mcp_tool` is async (matches the real MCP SDK's
     `ClientSession.call_tool`, which client.py already awaits), so
     execute_plan now uses `asyncio.gather` per batch instead of a thread
     pool.
  3. `context_facts` injects known IDs (location_id, requested_by, ...) into
     the planner prompt so the LLM never has to invent a staff_id/location_id
     — those come from the caller, not the model.
"""
from __future__ import annotations

import asyncio
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict

from .dag import Plan, Task, TaskKind


# TODO(team, only if the problem statement above turns out to be wrong):
# only this string and DEFAULT_TOOL_CATALOG below are problem-specific —
# nothing else in this file needs to change.
PLANNER_SYSTEM = """You are the restocking planner for Copperleaf Kitchen, a
multi-location restaurant chain. Produce a small executable DAG, not a prose
checklist. Every task must make a concrete contribution to restocking the
requested location's low-stock ingredients. Independent per-ingredient
research tasks should be parallel. The plan must end with exactly one
synthesis task (a restocking report) depending on every necessary branch.

Known facts you must use exactly as given, never invent your own values for them:
{context_facts}

For every task you must also choose a `kind`:
- "deterministic": a single, well-defined call to one of these MCP tools:
{tool_catalog}
  Set tool_name to the exact tool name and tool_args to its arguments.
- "ps": a single logical/computational step with one clear correct approach
  (e.g. computing how much budget remains, or how much of one ingredient to
  order given known stock and threshold) — no branching needed.
- "tot": deciding between several plausible restock priorities/suppliers
  before committing — a real branching decision (e.g. ranking several
  low-stock ingredients, or choosing among multiple candidate suppliers).
- "lats": placing a purchase order — an action whose success can be checked
  against the real server response (budget/verification), with retry and
  reflection on failure, not the model's own opinion of itself.
"""

DEFAULT_TOOL_CATALOG = """- list_low_stock_items(location_id: int) -> ingredients at/under reorder_threshold, with qty_on_hand
- list_suppliers() -> all suppliers with verified status and contact
- get_supplier(supplier_id: int) -> one supplier's verified status and contact
- place_purchase_order(ingredient_id: int, supplier_id: int, qty: int, unit_cost: float, requested_by: int) -> creates a PO; response includes requires_confirmation=True if the order exceeds 80% of the location's remaining budget or the supplier is unverified"""


class PlannedTask(BaseModel):
    """Wire schema; richer semantic constraints (cycle-freedom, tool binding)
    are enforced by the Task/Plan domain models in dag.py."""

    model_config = ConfigDict(extra="forbid")

    id: str
    instruction: str
    depends_on: list[str]
    kind: TaskKind
    tool_name: str | None = None
    tool_args: dict | None = None


class GeneratedPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str
    tasks: list[PlannedTask]


class MCPClient(Protocol):
    """Matches `CopperleafAgent.call_mcp_tool` in the memory/RAG agent's
    client.py exactly (same name, same async signature), so the planning
    agent can be handed the SAME live MCP session instead of standing up a
    second connection to mcp_server/."""

    async def call_mcp_tool(self, tool_name: str, arguments: dict) -> str: ...


class TaskExecutor(Protocol):
    """Implemented by Person 2's planning/router.py. Dispatches one
    non-deterministic sub-task by a plain lookup on `task.kind`
    ("ps" -> plan_and_solve, "tot" -> tree_of_thoughts, "lats" -> lats) and
    returns the sub-task's completed output as text. Person 2's job is that
    lookup plus flattening each algorithm's native return type (str for PS,
    list[Thought] for ToT, LATSResult for LATS) down to plain text — NOT
    deciding which algorithm a task needs, since `kind` already decided that.

    Note: plan_and_solve/tree_of_thoughts/lats (forked from the toolkit) are
    themselves sync (llm.invoke, not awaited). The router's __call__ just
    needs to be an `async def` wrapping those sync calls — no need to make
    the algorithms themselves async."""

    async def __call__(self, task: Task, plan: Plan | None, context: str) -> str: ...


async def stub_executor(task: Task, plan: Plan | None, context: str) -> str:
    """Temporary async stand-in for the real router so this module is
    buildable and testable before planning/router.py exists.

    DO NOT use this for the final comparison table / demo — swap in the real
    router (Person 2) before evaluation runs, or every "ps"/"tot"/"lats" task
    will look artificially cheap and instant in the results.
    """
    del plan, context
    return f"[STUB ROUTER] would solve '{task.id}' via {task.kind}: {task.instruction}"


def decompose_goal(
    goal: str,
    llm: BaseChatModel,
    context_facts: dict,
    tool_catalog: str = DEFAULT_TOOL_CATALOG,
) -> Plan:
    """context_facts example: {"location_id": 1, "requested_by": 2} — 2 is a
    kitchen_manager's staff_id; place_purchase_order rejects anyone else
    (see mcp_server/auth.py::require_kitchen_manager)."""
    facts_text = "\n".join(f"- {key}: {value}" for key, value in context_facts.items()) or "- None given."
    system = PLANNER_SYSTEM.format(context_facts=facts_text, tool_catalog=tool_catalog)
    generated = llm.with_structured_output(
        GeneratedPlan,
        method="json_schema",
    ).invoke([
        ("system", system),
        ("human", f"""Decompose this goal into 3-6 tasks: {goal!r}
Use short task ids such as t1. Dependencies may refer only to tasks in the plan.
Preserve the supplied goal exactly in the plan's goal field."""),
    ], temperature=0.1)
    payload = generated.model_dump()
    payload["goal"] = goal  # the caller's goal remains authoritative even if the model paraphrases it
    return Plan.model_validate(payload)


async def execute_plan(
    plan: Plan,
    mcp_client: MCPClient,
    executor: TaskExecutor = stub_executor,
) -> dict[str, str]:
    outputs: dict[str, str] = {}
    for batch in plan.execution_batches():
        calls = []
        task_ids = []
        for task_id in batch:
            task = plan.task(task_id)
            context = "\n\n".join(
                f"OUTPUT FROM {dependency}:\n{outputs[dependency]}"
                for dependency in task.depends_on
            ) or "No prerequisite outputs."
            if task.kind == "deterministic":
                calls.append(mcp_client.call_mcp_tool(task.tool_name, task.tool_args or {}))
            else:
                calls.append(executor(task, plan, context))
            task_ids.append(task_id)

        results = await asyncio.gather(*calls)
        for task_id, result in zip(task_ids, results):
            if not isinstance(result, str) or not result.strip():
                raise RuntimeError(f"Task '{task_id}' returned an empty or unsupported result")
            outputs[task_id] = result.strip()
    return outputs


def final_output(plan: Plan, outputs: dict[str, str]) -> str:
    terminals = plan.terminal_tasks()
    if len(terminals) != 1:
        raise ValueError(f"Expected exactly one terminal synthesis task, found {terminals}")
    return outputs[terminals[0]]
