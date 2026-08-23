"""
planning/router.py — dispatches a non-deterministic sub-task to PS / ToT /
LATS by a plain lookup on `task.kind`. Owned by Person 2.

This file is the ONLY place that decides which algorithm handles which
`kind` — and even here it's a lookup, not a judgment call, because the
judgment call already happened when the DAG/dynamic planner assigned `kind`
(see dag.py's TaskKind docstring for the full routing table). Satisfies the
`TaskExecutor` protocol in planning/decomposition.py, so it plugs in with a
single argument change:

    router = Router(llm, environment)
    outputs = await execute_plan(plan, mcp_client, executor=router.route)
"""
from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel

from .dag import Plan, Task
from .environment import RestockEnvironment
from .lats import lats
from .plan_and_solve import plan_and_solve
from .self_refine import reflect_and_refine
from .tree_of_thoughts import tree_of_thoughts


class Router:
    def __init__(self, llm: BaseChatModel, environment: RestockEnvironment):
        self.llm = llm
        self.environment = environment

    async def route(self, task: Task, plan: Plan | None, context: str) -> str:
        del plan  # not needed by any of PS/ToT/LATS today; kept for protocol symmetry
        question = f"Task: {task.instruction}\n\nContext:\n{context}"

        if task.kind == "ps":
            # Self-Refine wraps every "ps" result: cheap to redo, one draft +
            # one grounded critique + one revision (see self_refine.py).
            draft = plan_and_solve(question, self.llm)
            refined = reflect_and_refine(task.instruction, draft, self.llm)
            return refined.revised

        if task.kind == "tot":
            thoughts = tree_of_thoughts(question, self.llm)
            return thoughts[0].state if thoughts else "No viable option survived Tree-of-Thoughts search."

        if task.kind == "lats":
            result = await lats(question, self.llm, self.environment)
            return result.output

        raise ValueError(
            f"Router has no handler for kind={task.kind!r} "
            "('deterministic' tasks never reach the router — see decomposition.py::execute_plan)"
        )
