from .strategy import ContextStrategy
from .tokenizer import count_tokens


class ObservationMaskingStrategy(ContextStrategy):

    def __init__(self, keep_last_tool_outputs: int = 3):
        self.keep_last_tool_outputs = keep_last_tool_outputs
        self.name = (
            f"Observation masking "
            f"(keep last {keep_last_tool_outputs} tool outputs)"
        )

    def compress(
        self,
        turns: list[dict],
        scratchpad: dict | None = None,
    ) -> list[dict]:

        tool_indices = [
            i
            for i, turn in enumerate(turns)
            if turn.get("is_tool_output", False)
        ]

        keep_indices = set(
            tool_indices[-self.keep_last_tool_outputs:]
        )

        compressed = []

        for i, turn in enumerate(turns):

            new_turn = dict(turn)

            if (
                turn.get("is_tool_output", False)
                and i not in keep_indices
            ):
                token_count = count_tokens(
                    turn.get("content", "")
                )

                new_turn["content"] = (
                    f"[Tool output masked - "
                    f"{token_count} tokens omitted]"
                )

            compressed.append(new_turn)

        return compressed