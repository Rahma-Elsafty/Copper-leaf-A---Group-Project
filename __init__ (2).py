"""
planning/ — Decomposition & Planning agent implementation layer for the
Copperleaf Kitchen restocking agent. Complete: all 4 concerns wired.
Forked from github.com/AmrSheta22/task_decomposition_and_planning.

Ownership map (for the demo transcript / commit history):
  Person 1: dag.py, decomposition.py, dynamic_decomposition.py
  Person 2: plan_and_solve.py, tree_of_thoughts.py, lats.py, router.py
  Person 3: self_refine.py, reflexion.py, environment.py
  Person 4: planning_eval/ (separate top-level package, not part of this one)

Wiring note: `MCPClient` matches `CopperleafAgent.call_mcp_tool`
(agent/memory_rag_agent/client.py) exactly, so the planning agent can share
the memory/RAG agent's live `ClientSession` instead of opening a second MCP
connection. No LLM provider is hardcoded anywhere in this package — any
`langchain_core.BaseChatModel` works, chosen at the call site
(agent/planning_agent/main.py).

Typical wiring, once everything below is imported (see
agent/planning_agent/main.py for the full runnable version):

    environment = RestockEnvironment(mcp_client, requested_by=2)
    router = Router(llm, environment)

    # decomposition-first
    plan = decompose_goal(goal, llm, context_facts)
    outputs = await execute_plan(plan, mcp_client, executor=router.route)

    # dynamic / interleaved
    history = await dynamic_decomposition(goal, llm, mcp_client, context_facts, executor=router.route)

    # whole-run retry across trials (only when a single dynamic run isn't enough)
    result = await reflexion(goal, llm, mcp_client, context_facts, executor=router.route)
"""
from .dag import EnvironmentFeedback, Plan, Task, TaskKind, Thought
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
from .environment import RestockEnvironment
from .lats import LATSResult, PurchaseOrderCandidate, flatten_lats_tree, lats
from .plan_and_solve import plan_and_solve
from .reflexion import ReflexionResult, reflexion
from .router import Router
from .self_refine import ReflectionResult, deterministic_checks, reflect_and_refine
from .tree_of_thoughts import tree_of_thoughts

__all__ = [
    "DEFAULT_TOOL_CATALOG",
    "EnvironmentFeedback",
    "LATSResult",
    "MCPClient",
    "Plan",
    "PurchaseOrderCandidate",
    "ReflectionResult",
    "ReflexionResult",
    "RestockEnvironment",
    "Router",
    "Task",
    "TaskExecutor",
    "TaskKind",
    "Thought",
    "decompose_goal",
    "deterministic_checks",
    "dynamic_decomposition",
    "execute_plan",
    "final_output",
    "flatten_lats_tree",
    "lats",
    "plan_and_solve",
    "reflect_and_refine",
    "reflexion",
    "stub_executor",
    "tree_of_thoughts",
]
