from __future__ import annotations
import math
import re

from dataclasses import dataclass, field

from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel, ConfigDict, Field
from planning.models import EnvironmentFeedback
from planning.vendor.planning_lab.algorithms.environment import CopperleafEnvironment


# ============================================================
# LATS Structured Outputs
# ============================================================

class LATSAction(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    action: str = Field(min_length=2)
    state: str = Field(min_length=2)


class LATSActionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    actions: list[LATSAction] = Field(
        min_length=1,
        max_length=3,
    )


class ValueEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(
        ge=0.0,
        le=1.0,
    )


# ============================================================
# LATS Tree Node
# ============================================================

@dataclass
class LATSNode:
    state: str
    action: str = "root"

    parent: "LATSNode | None" = field(
        default=None,
        repr=False,
    )

    children: list["LATSNode"] = field(
        default_factory=list,
        repr=False,
    )

    visits: int = 0
    value_sum: float = 0.0

    environment_score: float = 0.0
    model_score: float = 0.0

    feedback: EnvironmentFeedback | None = None

    reflections: list[str] = field(
        default_factory=list,
    )

    @property
    def mean_value(self) -> float:
        if self.visits == 0:
            return 0.0

        return self.value_sum / self.visits


# ============================================================
# LATS Result
# ============================================================

@dataclass
class LATSResult:
    success: bool
    output: str
    best_score: float
    iterations: int
    root: LATSNode


# ============================================================
# UCT Selection
# ============================================================

def _uct(
    node: LATSNode,
    exploration_weight: float,
) -> float:

    if node.visits == 0:
        return float("inf")

    parent_visits = max(
        node.parent.visits if node.parent else 1,
        1,
    )

    return (
        node.mean_value
        + exploration_weight
        * math.sqrt(
            math.log(parent_visits)
            / node.visits
        )
    )


def _select_leaf(
    root: LATSNode,
    exploration_weight: float,
) -> LATSNode:

    node = root

    while node.children:
        node = max(
            node.children,
            key=lambda child: _uct(
                child,
                exploration_weight,
            ),
        )

    return node


# ============================================================
# Backpropagation
# ============================================================

def _backpropagate(
    node: LATSNode,
    value: float,
) -> None:

    current: LATSNode | None = node

    while current is not None:
        current.visits += 1
        current.value_sum += value
        current = current.parent


# ============================================================
# Collect Reflections Along Trajectory
# ============================================================

def _trajectory_reflections(
    node: LATSNode,
) -> list[str]:

    path: list[str] = []

    current: LATSNode | None = node

    while current is not None:
        path.extend(current.reflections)
        current = current.parent

    return list(reversed(path))


# ============================================================
# Main LATS Algorithm
# ============================================================

async def lats(
    task: str,
    llm: BaseChatModel,
    environment: Environment,
    iterations: int = 2,
    n_actions: int = 2,
    exploration_weight: float = 1.414,
) -> LATSResult:

    if iterations < 1:
        raise ValueError(
            "iterations must be positive"
        )

    if n_actions < 1:
        raise ValueError(
            "n_actions must be positive"
        )

    if n_actions > 3:
        raise ValueError(
            "n_actions cannot exceed 3"
        )

    # --------------------------------------------------------
    # Root
    # --------------------------------------------------------

    root = LATSNode(
        state="No attempt yet."
    )

    best = root

    completed_iterations = 0

    # --------------------------------------------------------
    # Search iterations
    # --------------------------------------------------------

    for iteration in range(
        1,
        iterations + 1,
    ):

        completed_iterations = iteration

        # ----------------------------------------------------
        # Selection
        # ----------------------------------------------------

        leaf = _select_leaf(
            root,
            exploration_weight,
        )

        # ----------------------------------------------------
        # Gather previous reflections
        # ----------------------------------------------------

        lessons = _trajectory_reflections(
            leaf
        )

        lesson_text = (
            "\n".join(
                f"- {item}"
                for item in lessons[-4:]
            )
            or "- None yet."
        )

        # ----------------------------------------------------
        # Expansion
        # ----------------------------------------------------

    response = llm.invoke(
        [
            (
                "system",
                """You are the action generator in LATS.

    Return ONLY valid JSON.
    Do not use Markdown.
    Do not use ``` fences.
    Do not add explanations.

    Required format:
    {
    "actions": [
        {
        "action": "short action name",
        "state": "complete candidate solution"
        }
    ]
    }
    """,
            ),
            (
                "human",
                f"""
    Task:
    {task}

    Current trajectory/state:
    {leaf.state}

    Reflections learned from failed branches:
    {lesson_text}

    Propose exactly {n_actions} distinct complete candidate solutions.

    Each state must contain a fully written concrete solution.
    Return JSON only.
    """,
            ),
        ],
        temperature=0.3,
    )

    content = response.content

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(
            "The chat model returned an empty response."
        )

    content = content.strip()

    # Handle accidental Markdown code fences
    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*",
            "",
            content,
            flags=re.IGNORECASE,
        )
        content = re.sub(
            r"\s*```$",
            "",
            content,
        ).strip()

    try:
        proposed = LATSActionBatch.model_validate_json(
            content
        )
    except Exception as exc:
        raise RuntimeError(
            "LATS action generator returned invalid JSON.\n\n"
            f"Model output:\n{content}\n\n"
            f"Validation error:\n{exc}"
        ) from exc

     
)

        for item in proposed.actions[:n_actions]:


            value_judgment = (
                llm
                .with_structured_output(
                    ValueEstimate,
                    method="json_schema",
                )
                .invoke(
                    [
                        (
                            "system",
                            "You are the LATS value function.",
                        ),
                        (
                            "human",
                            f"""
Task:
{task}

Candidate state:
{child.state}

External score:
{feedback.score}

External feedback:
{feedback.details}

Estimate the candidate's future usefulness.
Return a score between 0 and 1.
""",
                        ),
                    ],
                    temperature=0.1,
                )
            )

            child.model_score = (
                value_judgment.score
            )

            # ------------------------------------------------
            # Combined value
            # ------------------------------------------------

            combined_value = (
                0.75 * child.environment_score
                + 0.25 * child.model_score
            )

            # ------------------------------------------------
            # Reflection on failed branches
            # ------------------------------------------------

            if not feedback.success:

                response = llm.invoke(
                    [
                        (
                            "system",
                            (
                                "Create a branch-level LATS "
                                "reflection grounded in "
                                "environment feedback."
                            ),
                        ),
                        (
                            "human",
                            f"""
Task:
{task}

Action:
{child.action}

Resulting state:
{child.state}

External feedback:
{feedback.details}

Explain briefly why this branch failed
and how a later expansion should change.
""",
                        ),
                    ],
                    temperature=0.2,
                )

                reflection = response.content

                if (
                    not isinstance(
                        reflection,
                        str,
                    )
                    or not reflection.strip()
                ):
                    raise RuntimeError(
                        "The chat model returned an empty "
                        "or unsupported response"
                    )

                child.reflections.append(
                    reflection.strip()
                )

            # ------------------------------------------------
            # Backpropagation
            # ------------------------------------------------

            _backpropagate(
                child,
                combined_value,
            )

            # ------------------------------------------------
            # Track best candidate
            # ------------------------------------------------

            if (
                best is root
                or child.environment_score
                > best.environment_score
            ):
                best = child

            # ------------------------------------------------
            # Early success
            # ------------------------------------------------

            if feedback.success:

                return LATSResult(
                    success=True,
                    output=child.state,
                    best_score=child.environment_score,
                    iterations=completed_iterations,
                    root=root,
                )

    # --------------------------------------------------------
    # Search exhausted
    # --------------------------------------------------------

    return LATSResult(
        success=False,
        output=best.state,
        best_score=best.environment_score,
        iterations=completed_iterations,
        root=root,
    )


# ============================================================
# Flatten Tree
# ============================================================

def flatten_lats_tree(
    root: LATSNode,
) -> list[dict]:

    records: list[dict] = []

    queue: list[
        tuple[LATSNode, str | None]
    ] = [
        (root, None)
    ]

    next_id = 0

    while queue:

        node, parent_id = queue.pop(0)

        node_id = f"n{next_id}"
        next_id += 1

        records.append(
            {
                "id": node_id,
                "parent_id": parent_id,
                "action": node.action,
                "state": node.state,
                "visits": node.visits,
                "mean_value": node.mean_value,
                "environment_score": (
                    node.environment_score
                ),
                "model_score": node.model_score,
                "feedback": (
                    node.feedback.model_dump()
                    if node.feedback
                    else None
                ),
                "reflections": node.reflections,
            }
        )

        queue.extend(
            (child, node_id)
            for child in node.children
        )

    return records