from .sliding_window import SlidingWindowStrategy
from .observation_masking import ObservationMaskingStrategy
from .recursive_summarization import RecursiveSummarizationStrategy

from .llm_summarizer import summarize


STRATEGIES = [

    SlidingWindowStrategy(window_size=10),

    ObservationMaskingStrategy(
        keep_last_tool_outputs=3
    ),

    RecursiveSummarizationStrategy(
        keep_recent=6,
        summarizer=summarize
    )

]