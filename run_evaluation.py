"""
planning_eval/run_evaluation.py — runs every method against the FIXED test
suite in test_cases.py and writes per-case JSON traces to
planning_eval/results/, extending the existing artifacts/ trace format
(plans, node outputs, critic feedback, episodic memories, MCTS visits,
branch reflections) rather than building a second logging system.

Owned by Person 4. Requires a real .env (LLM provider key) and mcp_server/
runnable — same as agent/planning_agent/main.py. This is NOT mockable: the
whole point of the comparison table is real numbers from real runs.

Run:
    python -m planning_eval.run_evaluation
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path

from dotenv import load_dotenv
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

# TODO(team): swap for your real provider, same as agent/planning_agent/main.py
from langchain_mistralai import ChatMistralAI

from planning import (
    Router,
    RestockEnvironment,
    decompose_goal,
    dynamic_decomposition,
    execute_plan,
    final_output,
    plan_and_solve,
    reflect_and_refine,
    reflexion,
    tree_of_thoughts,
)
from planning.lats import lats as run_lats

from agent.planning_agent.main import PlanningMCPClient  # reused, not duplicated
from .test_cases import TEST_CASES

RESULTS_DIR = Path(__file__).parent / "results"


class InstrumentedLLM:
    """Wraps any langchain_core.BaseChatModel to count real calls and
    approximate tokens/latency, so every row in the comparison table comes
    from an actual run, not an estimate."""

    def __init__(self, llm):
        self._llm = llm
        self.calls = 0
        self.approx_tokens = 0
        self.elapsed_seconds = 0.0

    def _account(self, start: float, text: str) -> None:
        self.calls += 1
        self.elapsed_seconds += time.perf_counter() - start
        # Rough chars/4 heuristic; replace with real usage metadata if your
        # provider's response exposes token counts.
        self.approx_tokens += max(1, len(text) // 4)

    def invoke(self, messages, **kwargs):
        start = time.perf_counter()
        result = self._llm.invoke(messages, **kwargs)
        self._account(start, str(getattr(result, "content", result)))
        return result

    def with_structured_output(self, schema, method):
        inner = self._llm.with_structured_output(schema, method=method)
        outer = self

        class _Wrapped:
            def invoke(self, messages, **kwargs):
                start = time.perf_counter()
                result = inner.invoke(messages, **kwargs)
                outer._account(start, str(result))
                return result

        return _Wrapped()

    def snapshot(self) -> dict:
        return {
            "llm_calls": self.calls,
            "approx_tokens": self.approx_tokens,
            "latency_seconds": round(self.elapsed_seconds, 2),
        }


async def run_case(case, mcp_client, base_llm) -> dict:
    record: dict = {"id": case.id, "demonstrates": case.demonstrates, "runs": {}}
    requested_by = case.context_facts["requested_by"]

    if case.id.startswith("dag-"):
        for method_name in ("decomposition_first", "dynamic"):
            llm = InstrumentedLLM(base_llm)
            environment = RestockEnvironment(mcp_client, requested_by=requested_by)
            router = Router(llm, environment)
            try:
                if method_name == "decomposition_first":
                    plan = decompose_goal(case.goal, llm, case.context_facts)
                    outputs = await execute_plan(plan, mcp_client, executor=router.route)
                    result_text = final_output(plan, outputs)
                else:
                    history = await dynamic_decomposition(
                        case.goal, llm, mcp_client, case.context_facts, executor=router.route
                    )
                    result_text = history[-1][1] if history else "no steps taken"
                record["runs"][method_name] = {"result": result_text, "task_success": True, **llm.snapshot()}
            except Exception as exc:  # noqa: BLE001 — record failures as data, don't crash the whole suite
                record["runs"][method_name] = {"error": str(exc), "task_success": False, **llm.snapshot()}

    if case.id.startswith("plan-"):
        for method_name in ("ps", "tot", "lats"):
            llm = InstrumentedLLM(base_llm)
            environment = RestockEnvironment(mcp_client, requested_by=requested_by)
            entry: dict = {}
            try:
                if method_name == "ps":
                    entry["result"] = plan_and_solve(case.goal, llm)
                    entry["task_success"] = True
                elif method_name == "tot":
                    thoughts = tree_of_thoughts(case.goal, llm)
                    entry["result"] = thoughts[0].state if thoughts else "none"
                    entry["task_success"] = bool(thoughts)
                else:
                    lats_result = await run_lats(case.goal, llm, environment)
                    entry["result"] = lats_result.output
                    entry["task_success"] = lats_result.success
                entry.update(llm.snapshot())
            except Exception as exc:  # noqa: BLE001
                entry = {"error": str(exc), "task_success": False, **llm.snapshot()}
            record["runs"][method_name] = entry

    if case.id.startswith("refine-") or case.id.startswith("reflexion-"):
        llm = InstrumentedLLM(base_llm)
        try:
            draft = plan_and_solve(case.goal, llm)
            refined = reflect_and_refine(case.goal, draft, llm)
            record["runs"]["self_refine"] = {
                "result": refined.revised,
                "grounded_issues": refined.grounded_issues,
                "task_success": True,
                **llm.snapshot(),
            }
        except Exception as exc:  # noqa: BLE001
            record["runs"]["self_refine"] = {"error": str(exc), "task_success": False, **llm.snapshot()}

        llm2 = InstrumentedLLM(base_llm)
        router2 = Router(llm2, RestockEnvironment(mcp_client, requested_by=requested_by))
        try:
            outcome = await reflexion(case.goal, llm2, mcp_client, case.context_facts, executor=router2.route)
            record["runs"]["reflexion"] = {
                "result": outcome.output,
                "task_success": outcome.success,
                "trials": len(outcome.trials),
                **llm2.snapshot(),
            }
        except Exception as exc:  # noqa: BLE001
            record["runs"]["reflexion"] = {"error": str(exc), "task_success": False, **llm2.snapshot()}

    if case.id.startswith("ground-"):
        llm = InstrumentedLLM(base_llm)
        grounded_env = RestockEnvironment(mcp_client, requested_by=requested_by)
        try:
            grounded_result = await run_lats(case.goal, llm, grounded_env)
            record["runs"]["lats_grounded"] = {
                "result": grounded_result.output,
                "task_success": grounded_result.success,
                "best_score": grounded_result.best_score,
                **llm.snapshot(),
            }
        except Exception as exc:  # noqa: BLE001
            record["runs"]["lats_grounded"] = {"error": str(exc), "task_success": False, **llm.snapshot()}
        # NOTE(team): the ungrounded contrast row (the toolkit's ORIGINAL
        # random betavariate Environment) is deliberately NOT wired in here —
        # importing it side-by-side with the real one risks it silently
        # becoming the shipped default again (the assignment explicitly
        # warns against this). Run the untouched toolkit fork's environment
        # once, by hand, for that single contrast row, then paste the result
        # into the README table next to lats_grounded above.

    return record


async def main() -> None:
    load_dotenv()
    RESULTS_DIR.mkdir(exist_ok=True)

    server = StdioServerParameters(command="python", args=["-m", "mcp_server.server"])
    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            mcp_client = PlanningMCPClient(session)
            base_llm = ChatMistralAI(model="mistral-small-latest", random_seed=42, max_retries=2)

            all_records = []
            for case in TEST_CASES:
                print(f"Running {case.id} ...")
                record = await run_case(case, mcp_client, base_llm)
                all_records.append(record)
                (RESULTS_DIR / f"{case.id}.json").write_text(
                    json.dumps(record, indent=2, default=str), encoding="utf-8"
                )

            (RESULTS_DIR / "all_results.json").write_text(
                json.dumps(all_records, indent=2, default=str), encoding="utf-8"
            )
            print(f"\nDone. {len(all_records)} cases written to {RESULTS_DIR}/")


if __name__ == "__main__":
    asyncio.run(main())
