from .strategy import ContextStrategy


class SlidingWindowStrategy(ContextStrategy):

    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.name = f"Sliding window (last {window_size} turns)"

    def compress(
        self,
        turns: list[dict],
        scratchpad: dict | None = None,
    ) -> list[dict]:

        return [
            dict(turn)
            for turn in turns[-self.window_size:]
        ]