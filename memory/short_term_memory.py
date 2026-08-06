import json
from pathlib import Path
from collections import deque


LOG_FILE = Path("logs/short_term_memory_log.json")


class ShortTermMemory:

    def __init__(self, max_turns=4):
        self.messages = deque(maxlen=max_turns)

        self.scratchpad = {
            "plan": None,
            "current_subgoal": None,
            "reasoning": None,
            "variables": {}
        }

        LOG_FILE.parent.mkdir(exist_ok=True)

        if not LOG_FILE.exists():
            LOG_FILE.write_text("[]")

    def add(self, role, content):
        self.messages.append({
            "role": role,
            "content": content
        })

        self._log()

    def get_context(self):
        return list(self.messages)

    def update_plan(self, plan, subgoal):
        self.scratchpad["plan"] = plan
        self.scratchpad["current_subgoal"] = subgoal

        self._log()

    def update_reasoning(self, reasoning):
        self.scratchpad["reasoning"] = reasoning

        self._log()

    def set_variable(self, key, value):
        self.scratchpad["variables"][key] = value

        self._log()

    def get_scratchpad(self):
        return self.scratchpad

    def _log(self):

        state = {
            "messages": list(self.messages),
            "scratchpad": self.scratchpad
     }

        with open(LOG_FILE, "w") as f:
            json.dump(state, f, indent=4)