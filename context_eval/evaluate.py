import csv
import os
import time

from dotenv import load_dotenv
from openai import OpenAI

from .sliding_window import SlidingWindowStrategy
from .observation_masking import ObservationMaskingStrategy
from .recursive_summarization import RecursiveSummarizationStrategy
from .zone_based import ZoneBasedPruningStrategy

from .test_cases import build_test_suite
from .scratchpad import build_scratchpad
from .tokenizer import count_message_tokens


load_dotenv()


MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "nvidia/nemotron-3-super-120b-a12b:free",
)


client = OpenAI(
    api_key=os.getenv("OPENROUTER_API_KEY"),
    base_url="https://openrouter.ai/api/v1",
)


def generate_answer(messages: list[dict]):

    context = "\n".join(
        f"{m.get('role')}: {m.get('content')}"
        for m in messages
    )

    response = client.chat.completions.create(
        model=MODEL,
        temperature=0,
        messages=[
            {
                "role": "system",
                "content": """
You are an assistant for Copper Leaf Kitchen.

Answer the user's final question using the conversation
context.

Pay special attention to food allergies.

If the customer has a shellfish allergy, explicitly mention
that shellfish-containing dishes should not be recommended.
""",
            },
            {
                "role": "user",
                "content": context,
            },
        ],
    )

    answer = response.choices[0].message.content

    usage = response.usage

    return answer, {
        "input_tokens": getattr(
            usage,
            "prompt_tokens",
            0,
        ),
        "output_tokens": getattr(
            usage,
            "completion_tokens",
            0,
        ),
    }


def check_accuracy(answer: str) -> bool:

    answer = answer.lower()

    allergy_words = [
        "shellfish",
        "shrimp",
        "allergy",
        "allergic",
    ]

    return any(
        word in answer
        for word in allergy_words
    )


def evaluate_strategy(
    strategy,
    test_cases,
    scratchpad,
):

    results = []

    for case_number, turns in enumerate(
        test_cases,
        start=1,
    ):

        start_time = time.perf_counter()

        compressed = strategy.compress(
            turns,
            scratchpad,
        )

        compression_latency = (
            time.perf_counter() - start_time
        )

        input_tokens_before = count_message_tokens(
            turns
        )

        input_tokens_after = count_message_tokens(
            compressed
        )

        answer, usage = generate_answer(
            compressed
        )

        total_latency = (
            time.perf_counter() - start_time
        )

        accuracy = check_accuracy(answer)

        summary_output_tokens = 0

        for message in compressed:

            summary_usage = message.get(
                "_summary_usage"
            )

            if summary_usage:
                summary_output_tokens += (
                    summary_usage["output_tokens"]
                )

        total_output_tokens = (
            usage["output_tokens"]
            + summary_output_tokens
        )

        results.append({
            "case": case_number,
            "correct": accuracy,
            "input_before": input_tokens_before,
            "input_after": input_tokens_after,
            "output_tokens": total_output_tokens,
            "latency": total_latency,
            "compression_latency": compression_latency,
        })

    return results


def average(values):
    values = list(values)

    if not values:
        return 0

    return sum(values) / len(values)


def main():

    test_cases = build_test_suite()
    scratchpad = build_scratchpad()

    strategies = [
        SlidingWindowStrategy(
            window_size=10
        ),
        ObservationMaskingStrategy(
            keep_last_tool_outputs=3
        ),
        RecursiveSummarizationStrategy(
            keep_recent=6
        ),
        ZoneBasedPruningStrategy(
            early_keep=3,
            recent_keep=5
        ),
    ]

    final_rows = []

    print("\n" + "=" * 80)
    print("COPPER LEAF KITCHEN - CONTEXT EVALUATION")
    print("=" * 80)

    for strategy in strategies:

        print(
            f"\nRunning: {strategy.name}"
        )

        results = evaluate_strategy(
            strategy,
            test_cases,
            scratchpad,
        )

        accuracy = sum(
            r["correct"]
            for r in results
        )

        avg_input = average(
            r["input_after"]
            for r in results
        )

        avg_output = average(
            r["output_tokens"]
            for r in results
        )

        avg_latency = average(
            r["latency"]
            for r in results
        )

        row = {
            "strategy": strategy.name,
            "accuracy": f"{accuracy}/{len(results)}",
            "accuracy_rate": accuracy / len(results),
            "avg_input_tokens": round(avg_input),
            "avg_output_tokens": round(avg_output),
            "avg_latency_seconds": round(
                avg_latency,
                3,
            ),
        }

        final_rows.append(row)

        print(
            f"Accuracy: "
            f"{row['accuracy']}"
        )

        print(
            f"Avg input tokens: "
            f"{row['avg_input_tokens']}"
        )

        print(
            f"Avg output tokens: "
            f"{row['avg_output_tokens']}"
        )

        print(
            f"Avg latency: "
            f"{row['avg_latency_seconds']}s"
        )

    print("\n" + "=" * 80)
    print("FINAL COMPARISON")
    print("=" * 80)

    print(
        f"{'Strategy':45}"
        f"{'Accuracy':12}"
        f"{'Input':12}"
        f"{'Output':12}"
        f"{'Latency':12}"
    )

    for row in final_rows:

        print(
            f"{row['strategy'][:43]:45}"
            f"{row['accuracy']:12}"
            f"{row['avg_input_tokens']:12}"
            f"{row['avg_output_tokens']:12}"
            f"{row['avg_latency_seconds']:12.3f}"
        )

    os.makedirs(
        "context_eval/results",
        exist_ok=True,
    )

    output_file = (
        "context_eval/results/"
        "context_comparison.csv"
    )

    with open(
        output_file,
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=[
                "strategy",
                "accuracy",
                "accuracy_rate",
                "avg_input_tokens",
                "avg_output_tokens",
                "avg_latency_seconds",
            ],
        )

        writer.writeheader()
        writer.writerows(final_rows)

    print(
        f"\nResults saved to: {output_file}"
    )


if __name__ == "__main__":
    main()