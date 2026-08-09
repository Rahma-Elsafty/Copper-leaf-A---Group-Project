from .strategy import ContextStrategy
from .llm_summarizer import summarize


class RecursiveSummarizationStrategy(ContextStrategy):

    def __init__(
        self,
        keep_recent: int = 6,
    ):
        self.keep_recent = keep_recent
        self.name = (
            f"Recursive summarization "
            f"(keep last {keep_recent} turns)"
        )

    def compress(
        self,
        turns: list[dict],
        scratchpad: dict | None = None,
    ) -> list[dict]:

        if len(turns) <= self.keep_recent:
            return [
                dict(turn)
                for turn in turns
            ]

        old_turns = turns[:-self.keep_recent]
        recent_turns = turns[-self.keep_recent:]

        summary, usage = summarize(old_turns)

        summary_turn = {
            "role": "system",
            "content": (
                "Earlier conversation summary:\n"
                + summary
            ),
            "is_tool_output": False,
            "turn_index": -1,
            "_summary_usage": usage,
        }

        return [
            summary_turn,
            *[
                dict(turn)
                for turn in recent_turns
            ],
        ]

    def uses_llm_call(self) -> bool:
        return True