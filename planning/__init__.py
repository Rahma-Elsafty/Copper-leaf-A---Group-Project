"""
planning/ — Decomposition & Planning agent implementation layer for the
Copperleaf Kitchen restocking agent.
Forked from github.com/AmrSheta22/task_decomposition_and_planning.

Built by 4 people against the shared contracts defined here:
  - Task / Plan / TaskKind             -> planning/dag.py
  - MCPClient / TaskExecutor (async)   -> planning/decomposition.py

Ownership:
  Person 1 (this file's current exports): dag.py, decomposition.py, dynamic_decomposition.py
  Person 2 (adds): plan_and_solve.py, tree_of_thoughts.py, lats.py, router.py
  Person 3 (adds): self_refine.py, reflexion.py, environment.py
  Person 4:        planning_eval/ (separate package — test suite, run_evaluation.py, results/)

Wiring note: `MCPClient` is deliberately shaped to match
`CopperleafAgent.call_mcp_tool` (agent/memory_rag_agent/client.py) exactly,
so whoever builds agent/planning_agent/ can hand this package the SAME live
`ClientSession` the memory/RAG agent already opens — no second MCP
connection, no LLM provider hardcoded here (any langchain_core.BaseChatModel
works, chosen at the call site).

As Person 2 and Person 3 land their modules, add their public names to the
import list and __all__ below (mirrors the reference toolkit's own
algorithms/__init__.py pattern).
"""
from .dag import Plan, Task, TaskKind
from .decomposition import (
    DEFAULT_TOOL_CATALOG,
    MCPClient,
    TaskExecutor,
    decompose_goal,
    execute_plan,
    final_output,
    stub_executor,
)
from .dynamic_decomposition import dynamic_decomposition

__all__ = [
    "DEFAULT_TOOL_CATALOG",
    "MCPClient",
    "Plan",
    "Task",
    "TaskExecutor",
    "TaskKind",
    "decompose_goal",
    "dynamic_decomposition",
    "execute_plan",
    "final_output",
    "stub_executor",
]
