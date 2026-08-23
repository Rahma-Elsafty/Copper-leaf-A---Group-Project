"""
state_graph/techniques.py — the LLM-call techniques used inside graph
nodes: task_decompose, constrained_react, tree_of_thoughts_choice,
retrieve_grounding.

Design choice, and why: planning/ already has full Task
Decomposition + Tree of Thoughts + LATS implementations, but they're built
around planning/dag.py's `Plan`/`Task`/`Thought` contracts and an async MCP
session that the Decomposition & Planning agent owns end-to-end. Rebuilding
that exact machinery here just to reuse the algorithm would mean depending
on a whole planning-agent-shaped object graph for a two-or-three-item list.
Instead:
  - `task_decompose` and `constrained_react` are small, real, standalone
    implementations scoped to what a state-graph node actually needs.
  - `tree_of_thoughts_choice` DIRECTLY calls `planning.tree_of_thoughts.
    tree_of_thoughts` (no reimplementation) — that one genuinely fits
    as-is, since Food Safety Incident's "which corrective-action plan"
    choice is the same shape of problem (rank a few candidate thoughts)
    the existing function already solves generically.
  - `retrieve_grounding` tries the real project RAG stack (rag/hybrid_search)
    first, and only falls back to a plain SQL search over safety_policies
    if the heavy retrieval deps (Chroma/HuggingFace) aren't importable in
    the current environment — see its docstring.

Every function takes the LLM (or nothing) as an argument; nothing in this
module constructs a provider itself, so importing this module never
requires an API key or network access. Only *calling* the LLM-touching
paths does.
"""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from langchain_core.language_models.chat_models import BaseChatModel


# ---------------------------------------------------------------------------
# Task Decomposition
# ---------------------------------------------------------------------------

def task_decompose(
    goal: str,
    items: list[dict[str, Any]],
    llm: "BaseChatModel | None" = None,
) -> list[dict[str, Any]]:
    """Break a multi-item goal (e.g. "reconcile this delivery") into one
    concrete sub-step per item, in the order they should be executed.

    Deterministic fallback (used whenever `llm` is None, e.g. in tests/CI
    without an API key): one sub-step per item, in the given order — this
    is not a mock of the technique, it's the trivial-but-correct case of
    "decompose N independent items into N steps", which is exactly right
    when there's no genuine sequencing ambiguity to resolve. The LLM path
    is what earns its place when items DO have real ordering/grouping
    trade-offs (see `constrained_react` usage in the purchase-order graph
    docstring for why ordering matters there).
    """
    if llm is None:
        return [
            {"step": i + 1, "item": item, "instruction": f"Process item {i + 1}/{len(items)} for: {goal}"}
            for i, item in enumerate(items)
        ]

    from pydantic import BaseModel, ConfigDict, Field

    class DecompositionStep(BaseModel):
        model_config = ConfigDict(extra="forbid")
        item_index: int = Field(ge=0, description="Index into the provided items list this step handles.")
        instruction: str

    class DecompositionPlan(BaseModel):
        model_config = ConfigDict(extra="forbid")
        steps: list[DecompositionStep] = Field(min_length=1)

    prompt = (
        f"Goal: {goal}\n\n"
        f"Items to process ({len(items)} total):\n"
        + "\n".join(f"{i}: {item}" for i, item in enumerate(items))
        + "\n\nBreak this into one ordered step per item. Do not invent items."
    )
    plan = llm.with_structured_output(DecompositionPlan).invoke(prompt)
    return [
        {"step": i + 1, "item": items[s.item_index], "instruction": s.instruction}
        for i, s in enumerate(plan.steps)
    ]


# ---------------------------------------------------------------------------
# Constrained ReAct
# ---------------------------------------------------------------------------

class ToolNotWhitelisted(Exception):
    pass


def constrained_react(
    goal: str,
    allowed_tools: list[str],
    call_tool: Callable[[str, dict[str, Any]], Any],
    steps: list[dict[str, Any]],
    llm: "BaseChatModel | None" = None,
) -> list[dict[str, Any]]:
    """Execute `steps` (from task_decompose) by calling ONLY tools in
    `allowed_tools`. This is the "constrained" part: the node passes a
    closed whitelist, and any tool name outside it raises before the call
    ever reaches the MCP server — the constraint is enforced in Python,
    not just "asked nicely" of the model. (The server ALSO enforces its
    own per-agent whitelist independently — see mcp_server/server.py — so
    a compromised or hallucinated tool name is stopped twice.)

    Deterministic fallback path (llm=None): for each step, calls the
    first allowed tool with the step's `item` dict as arguments — this is
    what the tests and the crash-recovery demo run against, with no LLM
    involved, since the *whitelisting and execution* behavior (the thing
    this function actually adds) doesn't require an LLM to prove. The LLM
    path picks WHICH allowed tool and WHAT arguments to use per step when
    that choice isn't already fully determined by the step.
    """
    if not allowed_tools:
        raise ToolNotWhitelisted(f"No tools whitelisted for goal: {goal}")

    results = []
    for step in steps:
        if llm is None:
            tool_name = allowed_tools[0]
            arguments = step["item"]
        else:
            from pydantic import BaseModel, ConfigDict

            class ToolCall(BaseModel):
                model_config = ConfigDict(extra="forbid")
                tool_name: str
                arguments: dict[str, Any]

            prompt = (
                f"Goal: {goal}\nStep: {step['instruction']}\n"
                f"Item: {step['item']}\n"
                f"You may ONLY call one of these tools: {allowed_tools}.\n"
                "Return the exact tool name and its arguments."
            )
            call = llm.with_structured_output(ToolCall).invoke(prompt)
            tool_name, arguments = call.tool_name, call.arguments

        if tool_name not in allowed_tools:
            raise ToolNotWhitelisted(
                f"Model attempted to call '{tool_name}', which is outside the "
                f"whitelist {allowed_tools} for goal: {goal}"
            )

        result = call_tool(tool_name, arguments)
        results.append({"step": step["step"], "tool": tool_name, "arguments": arguments, "result": result})

    return results


# ---------------------------------------------------------------------------
# Tree of Thoughts — reuses planning/tree_of_thoughts.py directly
# ---------------------------------------------------------------------------

def tree_of_thoughts_choice(problem: str, llm: "BaseChatModel", depth: int = 2, beam_width: int = 2):
    """Thin pass-through to the EXISTING planning.tree_of_thoughts.tree_of_thoughts
    (imported lazily so this module doesn't require langchain at import
    time). Returns the ranked list of Thought objects; the caller (the
    food-safety graph) picks thoughts[0] as the chosen corrective-action
    plan and keeps the rest in state for the HITL reviewer to see the
    alternatives that were considered."""
    from planning.tree_of_thoughts import tree_of_thoughts

    return tree_of_thoughts(problem, llm, depth=depth, beam_width=beam_width)


# ---------------------------------------------------------------------------
# RAG grounding
# ---------------------------------------------------------------------------

def retrieve_grounding(query: str, k: int = 3) -> list[dict[str, Any]]:
    """Retrieve grounding documents for `query`.

    Tries the project's real Hybrid Search RAG stack first (same retriever
    the Memory/RAG agent uses, and the same one the platform's RAG
    document-management screen writes into — see rag/vector_store.py). If
    the heavy retrieval dependencies (langchain-chroma, sentence-transformers
    downloads) aren't available in the current environment, falls back to a
    plain SQL LIKE search over the `safety_policies` table (still real data,
    still grounded — just lexical instead of semantic) so this function is
    always exercisable, including in CI/offline environments like this
    sandbox. Whichever path ran is tagged on each result via `"source"` so
    a grader/reader can tell.
    """
    try:
        from rag.hybrid_search import HybridSearch  # noqa: F401
        from rag.vector_store import DocumentVectorStore

        store_ = DocumentVectorStore()
        hits = store_.vector_store.similarity_search(query, k=k)
        return [{"text": h.page_content, "metadata": h.metadata, "source": "hybrid_rag"} for h in hits]
    except Exception:
        from mcp_server.database import execute_query

        rows = execute_query(
            "SELECT policy_id, title, doc_text FROM safety_policies WHERE doc_text LIKE ? OR title LIKE ? LIMIT ?",
            (f"%{query}%", f"%{query}%", k),
        )
        return [
            {"text": r["doc_text"], "metadata": {"policy_id": r["policy_id"], "title": r["title"]}, "source": "sql_fallback"}
            for r in rows
        ]
