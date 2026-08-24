"""
planning/reflexion.py — Reflexion: retry the ENTIRE restocking attempt for a
location across multiple trials, carrying a bounded episodic buffer of
verbal reflections forward. This is the sub-task-type where a single retry
genuinely isn't enough — e.g. the first attempt only got half the low-stock
ingredients ordered before running into budget/verification problems, and
the agent needs to change its overall strategy for the whole run, not just
retry one purchase order.

Forked from algorithms/reflexion.py. Owned by Person 3.

How this differs from LATS: LATS backtracks WITHIN one purchase-order
placement (branch-level search over a single sub-task). Reflexion retries
the WHOLE dynamic_decomposition() run for the location, and is graded by a
grounded check over the REAL dynamic_decomposition() trace (every
place_purchase_order step must show requires_confirmation: False) — not a
self-report of "did I succeed".
"""
from __future__ import annotations

from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel

from .dag import EnvironmentFeedback
from .decomposition import MCPClient, TaskExecutor, stub_executor
from .dynamic_decomposition import dynamic_decomposition


@dataclass
class ReflexionTrial:
    number: int
    history: list[tuple[str, str]]
    feedback: EnvironmentFeedback
    reflection: str | None = None


@dataclass
class ReflexionResult:
    success: bool
    output: str
    trials: list[ReflexionTrial]
    memory: list[str]


def _grade_trial(history: list[tuple[str, str]]) -> EnvironmentFeedback:
    """Grounded check: reads the REAL dynamic_decomposition trace text for
    every purchase-order step and requires requires_confirmation: False on
    all of them. No model opinion involved — this is a string check against
    the actual server responses already captured in `history`."""
    po_steps = [
        result for _, result in history
        if "place_purchase_order" in result or "requires_confirmation" in result
    ]
    if not po_steps:
        return EnvironmentFeedback(success=False, score=0.0, details=["No purchase orders were placed."])
    failing = [step for step in po_steps if "'requires_confirmation': True" in step]
    if failing:
        return EnvironmentFeedback(
            success=False,
            score=max(0.0, 1.0 - len(failing) / len(po_steps)),
            details=[f"{len(failing)}/{len(po_steps)} orders required human confirmation."],
        )
    return EnvironmentFeedback(success=True, score=1.0, details=[])


async def reflexion(
    goal: str,
    llm: BaseChatModel,
    mcp_client: MCPClient,
    context_facts: dict,
    executor: TaskExecutor = stub_executor,
    max_trials: int = 3,
    memory_size: int = 3,
) -> ReflexionResult:
    if max_trials < 1 or memory_size < 1:
        raise ValueError("max_trials and memory_size must be positive")
    memory: list[str] = []
    trials: list[ReflexionTrial] = []
    best_history: list[tuple[str, str]] = []
    best_score = -1.0

    for number in range(1, max_trials + 1):
        recalled = "\n".join(f"- {item}" for item in memory[-memory_size:]) or "- No prior trials."
        run_goal = goal if not memory else f"{goal}\n\nLessons from previous failed attempts:\n{recalled}"

        history = await dynamic_decomposition(run_goal, llm, mcp_client, context_facts, executor=executor)
        feedback = _grade_trial(history)
        trial = ReflexionTrial(number=number, history=history, feedback=feedback)

        if feedback.score > best_score:
            best_history, best_score = history, feedback.score

        if feedback.success:
            trials.append(trial)
            summary = "\n".join(f"{task}: {result}" for task, result in history)
            return ReflexionResult(True, summary, trials, memory[-memory_size:])

        response = llm.invoke([
            ("system", "Generate a concise first-person Reflexion memory for a restocking retry, not a "
                       "revised plan. Ground it in the real feedback given, not speculation."),
            ("human", f"""Goal: {goal}
Trial trace:
{history}

External feedback (score {feedback.score}):
{chr(10).join('- ' + item for item in feedback.details)}

State what went wrong and the specific strategy to use next trial. Start with 'I'."""),
        ], temperature=0.2)
        reflection = response.content
        if not isinstance(reflection, str) or not reflection.strip():
            raise RuntimeError("The chat model returned an empty or unsupported response")
        reflection = reflection.strip()
        trial.reflection = reflection
        trials.append(trial)
        memory.append(reflection)

    summary = "\n".join(f"{task}: {result}" for task, result in best_history)
    return ReflexionResult(False, summary, trials, memory[-memory_size:])
