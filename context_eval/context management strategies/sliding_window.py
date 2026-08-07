from .strategy import ContextStrategy


class SlidingWindowStrategy(ContextStrategy):

    def __init__(self, window_size=10):
        self.window_size = window_size
        self.name = f"Sliding window (last {window_size} turns)"

    def compress(self, turns, scratchpad):

        return list(turns[-self.window_size:])