from abc import ABC, abstractmethod

class ContextStrategy(ABC):
    """
    Base class for all context window management strategies.
    """

    name = "base"

    @abstractmethod
    def compress(self, turns: list[dict], scratchpad: dict) -> list[dict]:
        """
        Return the compressed context that will be sent to the LLM.
        Must NOT modify the original turns or scratchpad.
        """
        raise NotImplementedError

    def uses_llm_call(self) -> bool:
        return False