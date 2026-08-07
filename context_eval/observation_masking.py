from .strategy import ContextStrategy
from .tokenizer import count_tokens


class ObservationMaskingStrategy(ContextStrategy):
 
    def __init__(self, keep_last_tool_outputs: int = 3):
        self.keep_last_tool_outputs = keep_last_tool_outputs
        self.name = f"Observation masking (keep last {keep_last_tool_outputs} tool outputs)"

    def compress(self, turns: list[dict], scratchpad: dict) -> list[dict]:
        tool_indices = [t["turn_index"] for t in turns if t["is_tool_output"]]
        keep_tool_indices = set(tool_indices[-self.keep_last_tool_outputs:]) if tool_indices else set()

        compressed = []
        for t in turns:
            if t["is_tool_output"] and t["turn_index"] not in keep_tool_indices:
                masked = dict(t)
                masked["content"] = (
                    f"[tool output masked - {count_tokens(t['content'])} tokens omitted, "
                    f"call #{t['turn_index']}]"
                )
                compressed.append(masked)
            else:
                compressed.append(t)
        return compressed
