from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, ConfigDict

class AgentStep(BaseModel):
    thought: str

    action: Literal[
        "call_tool",
        "respond",
        "replan"
    ]

    action_input: Optional[dict] = None

    final_answer: Optional[str] = None

    plan_updated: bool

    new_plan: Optional[str] = None

    next_subgoal: Optional[str] = None

class MemoryItem(BaseModel):
    """
    A single conversation item that may eventually leave
    the short-term memory buffer.
    """

    role: Literal["user", "assistant", "tool", "system"]

    content: str

    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(extra="forbid")


class MemoryRoutingDecision(BaseModel):
    """
    Decision returned by the Promote-or-Drop router.
    """

    destination: Literal["forget", "episodic"]

    reasoning: str

    importance_score: float = Field(
        ge=0,
        le=1,
        description="Estimated importance of the memory."
    )

    event_summary: Optional[str] = None

    context: Optional[str] = None

    outcome: Optional[str] = None

    category: Optional[
        Literal[
            "preference",
            "medical",
            "personal",
            "task",
            "fact",
            "other"
        ]
    ] = "other"

    model_config = ConfigDict(extra="forbid")
