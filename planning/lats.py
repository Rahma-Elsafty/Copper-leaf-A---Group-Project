"""
planning/lats.py — LATS (MCTS-guided search with grounded external feedback)
for "lats" sub-tasks: placing the restocking purchase orders.

Forked from algorithms/lats.py (AmrSheta22/task_decomposition_and_planning).
Owned by Person 2 (search algorithm); grounded by Person 3's
planning/environment.py via the `Environment` Protocol below — this file
only depends on that protocol, never on how grounding is implemented.

Adapted vs. the toolkit:
  1. `LATSAction` is now a structured `PurchaseOrderCandidate` (ingredient_id,
     supplier_id, qty, unit_cost) instead of a free-text `state` string, so
     the grounded environment can call `place_purchase_order` directly with
     exact arguments — no parsing natural language out of a candidate.
  2. `environment.evaluate(...)` is `async` (a real MCP tool call), so the
     whole search loop is `async def lats(...)`.
  3. UCT selection, backpropagation, and branch-level reflection-on-failure
     are otherwise unchanged from the toolkit.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Protocol

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field

from .dag import EnvironmentFeedback


class PurchaseOrderCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    action: str = Field(min_length=2, description="Human-readable summary of this candidate order.")
    ingredient_id: int
    supplier_id: int
    qty: int = Field(gt=0)
    unit_cost: float = Field(gt=0)


class LATSActionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[PurchaseOrderCandidate] = Field(min_length=1, max_length=3)


class ValueEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=1.0)


class Environment(Protocol):
    """Implemented by planning/environment.py (Person 3)."""

    async def evaluate(self, candidate: PurchaseOrderCandidate) -> EnvironmentFeedback: ...


@dataclass
class LATSNode:
    candidate: PurchaseOrderCandidate | None
    action: str = "root"
    parent: "LATSNode | None" = field(default=None, repr=False)
    children: list["LATSNode"] = field(default_factory=list, repr=False)
    visits: int = 0
    value_sum: float = 0.0
    environment_score: float = 0.0
    model_score: float = 0.0
    feedback: EnvironmentFeedback | None = None
    reflections: list[str] = field(default_factory=list)

    @property
    def mean_value(self) -> float:
        return self.value_sum / self.visits if self.visits else 0.0


@dataclass
class LATSResult:
    success: bool
    output: str
    best_score: float
    iterations: int
    root: LATSNode


def _uct(node: LATSNode, exploration_weight: float) -> float:
    if node.visits == 0:
        return float("inf")
    parent_visits = max(node.parent.visits if node.parent else 1, 1)
    return node.mean_value + exploration_weight * math.sqrt(math.log(parent_visits) / node.visits)


def _select_leaf(root: LATSNode, exploration_weight: float) -> LATSNode:
    node = root
    while node.children:
        node = max(node.children, key=lambda child: _uct(child, exploration_weight))
    return node


def _backpropagate(node: LATSNode, value: float) -> None:
    while node is not None:
        node.visits += 1
        node.value_sum += value
        node = node.parent


def _trajectory_reflections(node: LATSNode) -> list[str]:
    path: list[str] = []
    while node is not None:
        path.extend(node.reflections)
        node = node.parent
    return list(reversed(path))


async def lats(
    task: str,
    llm: BaseChatModel,
    environment: Environment,
    iterations: int = 2,
    n_actions: int = 2,
    exploration_weight: float = 1.414,
) -> LATSResult:
    if iterations < 1 or n_actions < 1:
        raise ValueError("iterations and n_actions must be positive")
    root = LATSNode(candidate=None, action="root")
    best = root
    completed_iterations = 0
    for iteration in range(1, iterations + 1):
        completed_iterations = iteration
        leaf = _select_leaf(root, exploration_weight)
        lessons = _trajectory_reflections(leaf)
        lesson_text = "\n".join(f"- {item}" for item in lessons[-4:]) or "- None yet."
        proposed = llm.with_structured_output(
            LATSActionBatch,
            method="json_schema",
        ).invoke([
            ("system", "You are the action generator in LATS for Copperleaf Kitchen's restocking agent. "
                       "Propose real, distinct candidate purchase orders using ONLY ingredient_id and "
                       "supplier_id values explicitly mentioned in the task context — never invent IDs."),
            ("human", f"""Task: {task}
Reflections learned from failed branches:
{lesson_text}

Propose exactly {n_actions} distinct candidate purchase order(s)."""),
        ], temperature=0.5)
        for candidate in proposed.actions[:n_actions]:
            child = LATSNode(candidate=candidate, action=candidate.action, parent=leaf)
            leaf.children.append(child)
            feedback = await environment.evaluate(candidate)
            child.feedback = feedback
            child.environment_score = feedback.score
            value_judgment = llm.with_structured_output(
                ValueEstimate,
                method="json_schema",
            ).invoke([
                ("system", "You are the LATS value function."),
                ("human", f"""Task: {task}
Candidate: {candidate.model_dump()}
External score: {feedback.score}
External feedback: {feedback.details}
Estimate the candidate's future usefulness."""),
            ], temperature=0.1)
            child.model_score = value_judgment.score
            combined_value = 0.75 * child.environment_score + 0.25 * child.model_score
            if not feedback.success:
                response = llm.invoke([
                    ("system", "Create a branch-level LATS reflection grounded in the real server feedback."),
                    ("human", f"""Task: {task}
Candidate: {candidate.model_dump()}
External feedback: {feedback.details}
Explain briefly why this branch failed and how a later expansion should change."""),
                ], temperature=0.2)
                reflection = response.content
                if not isinstance(reflection, str) or not reflection.strip():
                    raise RuntimeError("The chat model returned an empty or unsupported response")
                child.reflections.append(reflection.strip())
            _backpropagate(child, combined_value)
            if best.candidate is None or child.environment_score > best.environment_score:
                best = child
            if feedback.success:
                return LATSResult(True, candidate.action, child.environment_score, completed_iterations, root)
    best_text = best.action if best.candidate else "No successful candidate found."
    return LATSResult(False, best_text, best.environment_score, completed_iterations, root)


def flatten_lats_tree(root: LATSNode) -> list[dict]:
    records: list[dict] = []
    queue: list[tuple[LATSNode, str | None]] = [(root, None)]
    next_id = 0
    while queue:
        node, parent_id = queue.pop(0)
        node_id = f"n{next_id}"
        next_id += 1
        records.append({
            "id": node_id,
            "parent_id": parent_id,
            "action": node.action,
            "candidate": node.candidate.model_dump() if node.candidate else None,
            "visits": node.visits,
            "mean_value": node.mean_value,
            "environment_score": node.environment_score,
            "model_score": node.model_score,
            "feedback": node.feedback.model_dump() if node.feedback else None,
            "reflections": node.reflections,
        })
        queue.extend((child, node_id) for child in node.children)
    return records
