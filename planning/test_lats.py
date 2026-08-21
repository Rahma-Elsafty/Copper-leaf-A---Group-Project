from __future__ import annotations

import asyncio

from langchain_openai import ChatOpenAI

from planning.vendor.planning_lab.algorithms.lats import (
    lats,
    flatten_lats_tree,
)
from planning.vendor.planning_lab.algorithms.environment import (
    EnvironmentFeedback,
)

import os
from langchain_openai import ChatOpenAI




class FakeEnvironment:
    """
    Simple deterministic environment for testing LATS.

    A candidate succeeds if its state contains
    the word 'VALID'.
    """

    async def evaluate(self, state: str) -> EnvironmentFeedback:

        if "VALID" in state.upper():
            return EnvironmentFeedback(
                success=True,
                score=1.0,
                details=[
                    "Candidate contains a valid solution."
                ],
            )

        return EnvironmentFeedback(
            success=False,
            score=0.2,
            details=[
                "Candidate does not contain a valid solution."
            ],
        )


# ============================================================
# Main Test
# ============================================================

async def main():

    print("=" * 60)
    print(" Copperleaf LATS Test")
    print("=" * 60)

    # --------------------------------------------------------
    # LLM
    # --------------------------------------------------------

 
    llm = ChatOpenAI(
        model=os.getenv("COPPERLEAF_LLM_MODEL", "openai/gpt-oss-20b:free"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url=os.getenv(
            "COPPERLEAF_LLM_BASE_URL",
            "https://openrouter.ai/api/v1",
        ),
        temperature=0.2,
    )

    # --------------------------------------------------------
    # Environment
    # --------------------------------------------------------

    environment = FakeEnvironment()

    # --------------------------------------------------------
    # Task
    # --------------------------------------------------------

    task = """
Determine a valid purchasing decision for a restaurant.

The final candidate must contain a concrete valid solution.
"""

    print("\nTASK:")
    print(task)

    print("\nRunning LATS...\n")

    # --------------------------------------------------------
    # Run LATS
    # --------------------------------------------------------

    result = await lats(
        task=task,
        llm=llm,
        environment=environment,
        iterations=2,
        n_actions=2,
        exploration_weight=1.414,
    )

    # --------------------------------------------------------
    # Result
    # --------------------------------------------------------

    print("=" * 60)
    print(" LATS RESULT")
    print("=" * 60)

    print(f"\nSuccess: {result.success}")
    print(f"Best score: {result.best_score}")
    print(f"Iterations: {result.iterations}")

    print("\nBest output:")
    print(result.output)

    # --------------------------------------------------------
    # Tree
    # --------------------------------------------------------

    print("\n" + "=" * 60)
    print(" LATS TREE")
    print("=" * 60)

    tree = flatten_lats_tree(result.root)

    for node in tree:

        print(f"""
Node: {node["id"]}
Parent: {node["parent_id"]}
Action: {node["action"]}
Visits: {node["visits"]}
Mean value: {node["mean_value"]:.3f}
Environment score: {node["environment_score"]:.3f}
Model score: {node["model_score"]:.3f}
Feedback: {node["feedback"]}
Reflections: {node["reflections"]}
State:
{node["state"]}
""")

    # --------------------------------------------------------
    # Assertions
    # --------------------------------------------------------

    assert result.iterations >= 1

    assert result.output

    assert len(tree) >= 2

    print("=" * 60)
    print(" TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())