from .strategy import ContextStrategy
from .tokenizer import count_tokens


class ObservationMaskingStrategy(ContextStrategy):

    def __init__(self, keep_last_tool_outputs=3):

        self.keep_last_tool_outputs = keep_last_tool_outputs

        self.name = (
            f"Observation masking (keep last {keep_last_tool_outputs} tool outputs)"
        )

    def compress(self, turns, scratchpad):

        tool_indices = [

            i

            for i, turn in enumerate(turns)

            if turn.get("is_tool_output", False)

        ]

        keep_tool_indices = set(
            tool_indices[-self.keep_last_tool_outputs:]
        )

        compressed = []

        for i, turn in enumerate(turns):

            if (
                turn.get("is_tool_output", False)

                and

                i not in keep_tool_indices
            ):

                masked = dict(turn)

                masked["content"] = (
                    f"[Tool output masked - "
                    f"{count_tokens(turn['content'])} tokens omitted]"
                )

                compressed.append(masked)

            else:

                compressed.append(dict(turn))

        return compressed