from __future__ import annotations

import asyncio

from langchain_openai import ChatOpenAI

from planning.vendor.planning_lab.lats import (
    lats,
    flatten_lats_tree,
)

from planning.vendor.planning_lab.models import (
    EnvironmentFeedback,
)


class FakeEnvironment:
    """
    Simple deterministic environment for testing LATS.
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


async def main():

    print("=" * 60)
    print(" Copperleaf LATS Test")
    print("=" * 60)

    llm = ChatOpenAI(
        model="openai/gpt-oss-20b:free",
        temperature=0.2,
        base_url="https://openrouter.ai/api/v1",
    )

    environment = FakeEnvironment()

    task = """
Determine a valid purchasing decision for a restaurant.

The final candidate must contain a concrete valid solution.
"""

    print("\nTASK:")
    print(task)

    print("\nRunning LATS...\n")

    result = await lats(
        task=task,
        llm=llm,
        environment=environment,
        iterations=2,
        n_actions=2,
        exploration_weight=1.414,
    )

    print("=" * 60)
    print(" LATS RESULT")
    print("=" * 60)

    print(f"\nSuccess: {result.success}")
    print(f"Best score: {result.best_score}")
    print(f"Iterations: {result.iterations}")

    print("\nBest output:")
    print(result.output)

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

    assert result.output
    assert result.iterations >= 1
    assert len(tree) >= 2

    print("=" * 60)
    print(" TEST PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())