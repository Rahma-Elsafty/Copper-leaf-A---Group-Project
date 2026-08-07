from .strategy import ContextStrategy

COMPACT_PROMPT = """
Summarize the conversation below.

Preserve:
- decisions made
- unresolved issues
- key findings
- user preferences
- important constraints

Discard:
- redundant tool output
- superseded reasoning
- repetitive information
"""


class RecursiveSummarizationStrategy(ContextStrategy):

    def __init__(self, keep_recent=6, summarizer=None):
        self.keep_recent = keep_recent
        self.summarizer = summarizer
        self.name = (
            f"Recursive summarization (keep last {keep_recent} turns)"
        )

    def compress(self, turns, scratchpad):

        if len(turns) <= self.keep_recent:
            return list(turns)

        old = turns[:-self.keep_recent]
        recent = turns[-self.keep_recent:]

        if self.summarizer is None:
            summary = "[Conversation summary unavailable]"
        else:
            summary = self.summarizer(COMPACT_PROMPT, old)

        summary_turn = {
            "role": "system",
            "content": f"Earlier context:\n{summary}",
            "is_tool_output": False,
            "turn_index": -1,
        }

        return [summary_turn] + list(recent)

    def uses_llm_call(self):
        return True