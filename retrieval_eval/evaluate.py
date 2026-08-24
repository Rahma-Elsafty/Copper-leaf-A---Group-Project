
import csv
import json
import time
from pathlib import Path

from .tokenizer import count_tokens


def normalize(text):
    return " ".join(
        str(text)
        .lower()
        .strip()
        .split()
    )


def get_document_text(documents):
    if not documents:
        return ""

    return " ".join(
        normalize(
            getattr(
                doc,
                "page_content",
                str(doc),
            )
        )
        for doc in documents
    )


def keyword_matches(text, expected_keywords):
    text = normalize(text)

    return {
        keyword: normalize(keyword) in text
        for keyword in expected_keywords
    }


def all_keywords_present(text, expected_keywords):
    if not expected_keywords:
        return False

    matches = keyword_matches(
        text,
        expected_keywords,
    )

    return all(matches.values())


def retrieval_is_correct(
    documents,
    expected_keywords,
):
    document_text = get_document_text(
        documents
    )

    return all_keywords_present(
        document_text,
        expected_keywords,
    )


def answer_is_correct(
    answer,
    expected_keywords,
):
    return all_keywords_present(
        answer,
        expected_keywords,
    )


def evaluate(
    questions,
    architectures,
):

    detailed = []
    summary = {}

    for architecture_name, runner in architectures.items():

        print("\n")
        print("=" * 70)
        print(
            f"EVALUATING: {architecture_name}"
        )
        print("=" * 70)

        correct_answers = 0
        correct_retrievals = 0

        total_latency = 0
        total_input_tokens = 0
        total_output_tokens = 0

        for question in questions:

            query = question["question"]

            expected_keywords = question.get(
                "expected_keywords",
                [],
            )

            start = time.perf_counter()

            try:

                result = runner(query)

                if isinstance(result, tuple):

                    answer = result[0]

                    documents = (
                        result[1]
                        if len(result) > 1
                        else []
                    )

                else:

                    answer = result
                    documents = []

            except Exception as e:

                answer = (
                    f"ERROR: "
                    f"{type(e).__name__}: {e}"
                )

                documents = []

            latency = (
                time.perf_counter()
                - start
            )

            input_tokens = count_tokens(
                query
            )

            output_tokens = count_tokens(
                answer
            )

            answer_correct = answer_is_correct(
                answer,
                expected_keywords,
            )

            retrieval_correct = retrieval_is_correct(
                documents,
                expected_keywords,
            )

            if answer_correct:
                correct_answers += 1

            if retrieval_correct:
                correct_retrievals += 1

            total_latency += latency
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens

            answer_matches = keyword_matches(
                answer,
                expected_keywords,
            )

            retrieval_matches = keyword_matches(
                get_document_text(documents),
                expected_keywords,
            )

            detailed.append(
                {
                    "architecture": architecture_name,
                    "question_id": question.get(
                        "id",
                        "",
                    ),
                    "category": question.get(
                        "category",
                        "",
                    ),
                    "question": query,
                    "expected_keywords": expected_keywords,
                    "answer": answer,
                    "retrieved_documents": len(
                        documents
                    ),
                    "answer_correct": answer_correct,
                    "retrieval_correct": retrieval_correct,
                    "answer_matches": json.dumps(
                        answer_matches
                    ),
                    "retrieval_matches": json.dumps(
                        retrieval_matches
                    ),
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "latency_seconds": round(
                        latency,
                        3,
                    ),
                }
            )

            print(
                f"\n[{question.get('id', '')}]"
            )

            print(
                f"Answer: {answer[:300]}"
            )

            print(
                f"Retrieved: {len(documents)} docs | "
                f"Answer correct: {answer_correct} | "
                f"Retrieval correct: {retrieval_correct}"
            )

            print(
                f"Input: {input_tokens} | "
                f"Output: {output_tokens} | "
                f"Latency: {latency:.2f}s"
            )

        total = len(questions)

        summary[architecture_name] = {

            "accuracy": (
                correct_answers / total
                if total
                else 0
            ),

            "retrieval_accuracy": (
                correct_retrievals / total
                if total
                else 0
            ),

            "correct": correct_answers,

            "retrieval_correct": (
                correct_retrievals
            ),

            "total": total,

            "avg_input_tokens": (
                total_input_tokens / total
                if total
                else 0
            ),

            "avg_output_tokens": (
                total_output_tokens / total
                if total
                else 0
            ),

            "avg_latency": (
                total_latency / total
                if total
                else 0
            ),
        }

    return detailed, summary


def print_summary(summary):

    print("\n")
    print("=" * 110)
    print(
        "RETRIEVAL ARCHITECTURE EVALUATION"
    )
    print("=" * 110)

    print(
        f"{'Architecture':<20}"
        f"{'Answer Acc.':<15}"
        f"{'Retrieval Acc.':<17}"
        f"{'Avg Input':<15}"
        f"{'Avg Output':<15}"
        f"{'Avg Latency':<15}"
    )

    print("-" * 110)

    for name, result in summary.items():

        print(
            f"{name:<20}"
            f"{result['accuracy'] * 100:.1f}%"
            f"{'':<10}"
            f"{result['retrieval_accuracy'] * 100:.1f}%"
            f"{'':<12}"
            f"{result['avg_input_tokens']:.0f}"
            f"{'':<10}"
            f"{result['avg_output_tokens']:.0f}"
            f"{'':<10}"
            f"{result['avg_latency']:.2f}s"
        )

    print("=" * 110)


def save_results(
    detailed,
    summary,
):

    output_dir = Path(
        "retrieval_eval"
    )

    output_dir.mkdir(
        exist_ok=True
    )

    csv_path = (
        output_dir
        / "retrieval_results.csv"
    )

    if detailed:

        with csv_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=detailed[0].keys(),
            )

            writer.writeheader()
            writer.writerows(detailed)

    json_path = (
        output_dir
        / "retrieval_summary.json"
    )

    with json_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            summary,
            f,
            indent=2,
        )

    readme_path = (
        output_dir
        / "README.md"
    )

    with readme_path.open(
        "w",
        encoding="utf-8",
    ) as f:

        f.write(
            "# Retrieval Architecture Evaluation\n\n"
        )

        f.write(
            "| Architecture | Answer Accuracy | "
            "Retrieval Accuracy | Avg Input Tokens | "
            "Avg Output Tokens | Avg Latency |\n"
        )

        f.write(
            "|---|---:|---:|---:|---:|\n"
        )

        for name, result in summary.items():

            f.write(
                f"| {name} | "
                f"{result['accuracy'] * 100:.1f}% | "
                f"{result['retrieval_accuracy'] * 100:.1f}% | "
                f"{result['avg_input_tokens']:.0f} | "
                f"{result['avg_output_tokens']:.0f} | "
                f"{result['avg_latency']:.2f}s |\n"
            )

    print(
        "\nResults saved to:"
        f"\n  {csv_path}"
        f"\n  {json_path}"
        f"\n  {readme_path}"
    )
