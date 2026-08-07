import json

class ContextManager:
    def __init__(self, scratchpad=""):
        self.scratchpad = scratchpad

    def apply_sliding_window(self, messages, window_size=10):
        """تحتفظ فقط بآخر N مسجات مع الحفاظ على الـ Scratchpad"""
        return {
            "scratchpad": self.scratchpad,
            "messages": messages[-window_size:]
        }

    def apply_observation_masking(self, messages, keep_last_n_tools=3):
        """تخفي مخرجات الـ Tools القديمة (JSON bloat) مع الحفاظ على الحوار"""
        pruned_messages = []
        tool_count = 0
        for msg in reversed(messages):
            if msg.get("role") == "tool":
                tool_count += 1
                if tool_count > keep_last_n_tools:
                    pruned_messages.append({"role": "tool", "content": "[Observation Masked]"})
                    continue
            pruned_messages.append(msg)
        return {
            "scratchpad": self.scratchpad,
            "messages": list(reversed(pruned_messages))
        }

    def apply_recursive_summarization(self, messages, llm_client, threshold=15):
        """بتلخص الحوارات القديمة لما تعدي العتبة"""
        if len(messages) <= threshold:
            return {"scratchpad": self.scratchpad, "messages": messages}
        
        old_messages = messages[:-5]
        recent_messages = messages[-5:]
        summary_prompt = f"Summarize key decisions/details from this history: {json.dumps(old_messages)}"
        summary = llm_client.generate(summary_prompt) # استدعي الـ LLM اللي شغالين بيه
        
        return {
            "scratchpad": self.scratchpad,
            "messages": [{"role": "system", "content": f"Summary of earlier transcript: {summary}"}] + recent_messages
        }
