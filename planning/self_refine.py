"""
planning/self_refine.py — Self-Refine (one draft, one critique against a
rubric, one revision) for "ps" sub-task outputs — cheap to redo, wired
inline by router.py right after plan_and_solve() returns.

Forked from algorithms/self_refine.py. Owned by Person 3 (grounded vs.
ungrounded critique concern).

Grounded check for this domain: `deterministic_checks` no longer just
counts words — it fails a draft that contains no numbers at all (restocking
math — qty, cost, budget — is always expected from a "ps" task) and a draft
that doesn't reference any of the task's own significant terms. This catches
a class of failure an LLM asked "are you happy with this?" reliably misses:
a fluent-sounding answer that never actually did the arithmetic.
"""
import re
from dataclasses import dataclass

from langchain_core.language_models.chat_models import BaseChatModel


def deterministic_checks(goal: str, draft: str) -> list[str]:
    issues: list[str] = []
    if len(draft.split()) < 8:
        issues.append("The deliverable looks too short to contain a real calculation or decision.")
    if not re.search(r"\d", draft):
        issues.append("The deliverable contains no numbers — restocking math (qty, cost, budget) is expected.")
    goal_terms = {
        word.lower()
        for word in re.findall(r"[A-Za-z]{5,}", goal)
        if word.lower() not in {"create", "design", "write", "build", "about", "using", "compute", "decide"}
    }
    represented = [term for term in goal_terms if term in draft.lower()]
    if goal_terms and not represented:
        issues.append("The output contains none of the task's significant terms.")
    return issues


@dataclass
class ReflectionResult:
    draft: str
    critique: str
    revised: str
    grounded_issues: list[str]


def reflect_and_refine(goal: str, draft: str, llm: BaseChatModel) -> ReflectionResult:
    grounded = deterministic_checks(goal, draft)
    grounded_report = "\n".join(f"- {issue}" for issue in grounded) or "- Deterministic checks passed."
    critique_response = llm.invoke([
        ("system", "You are a separate critic for Copperleaf Kitchen's restocking agent. Judge against the "
                   "rubric: correctness, completeness, internal consistency, and instruction adherence. "
                   "Do not rewrite the draft."),
        ("human", f"""Goal: {goal}
External deterministic checks:
{grounded_report}

Draft:
{draft}

List concrete issues. If there are none, respond exactly PASS."""),
    ], temperature=0.2)
    critique = critique_response.content
    if not isinstance(critique, str) or not critique.strip():
        raise RuntimeError("The chat model returned an empty or unsupported response")
    critique = critique.strip()
    if critique.upper() == "PASS" and not grounded:
        revised = draft
    else:
        response = llm.invoke([
            ("system", "Revise a restocking sub-task deliverable using both external checks and an "
                       "independent critique."),
            ("human", f"Goal: {goal}\n\nDraft:\n{draft}\n\nGrounded checks:\n{grounded_report}\n\nCritique:\n{critique}\n\nReturn only the improved deliverable."),
        ], temperature=0.2)
        revised = response.content
        if not isinstance(revised, str) or not revised.strip():
            raise RuntimeError("The chat model returned an empty or unsupported response")
        revised = revised.strip()
    return ReflectionResult(draft, critique, revised, grounded)
