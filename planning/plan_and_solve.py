"""
planning/plan_and_solve.py — Plan-and-Solve prompting for single-pass ("ps")
restocking sub-tasks: one clear correct approach, no branching (e.g.
computing how much of an ingredient to order given known stock and a
target, or working out remaining budget from figures already gathered by
earlier DAG nodes).

Forked from algorithms/plan_and_solve.py — algorithmically unchanged; this
step never touches MCP/DB itself, it only reasons over the context
(dependency outputs) the DAG executor already gathered, which is why it's
cheap and appropriate for a single deterministic-shaped calculation.
"""
from langchain_core.language_models.chat_models import BaseChatModel


def plan_and_solve(question: str, llm: BaseChatModel) -> str:
    response = llm.invoke([
        ("system", "You use Plan-and-Solve prompting for Copperleaf Kitchen's restocking agent. "
                    "Clearly separate PLAN from SOLUTION. Use only the facts given in the question — "
                    "never invent ingredient names, IDs, prices, or budget figures."),
        ("human", f"""{question}

First understand the problem and devise a plan to solve it. Then carry out the
plan step by step. Check calculations and common-sense assumptions."""),
    ], temperature=0.2)
    if not isinstance(response.content, str) or not response.content.strip():
        raise RuntimeError("The chat model returned an empty or unsupported response")
    return response.content.strip()
