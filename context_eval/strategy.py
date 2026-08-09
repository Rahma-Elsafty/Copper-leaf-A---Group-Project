from abc import ABC, abstractmethod


class ContextStrategy(ABC):
    name = "base"

    @abstractmethod
    def compress(
        self,
        turns: list[dict],
        scratchpad: dict | None = None,
    ) -> list[dict]:
        raise NotImplementedError

    def uses_llm_call(self) -> bool:
        return False