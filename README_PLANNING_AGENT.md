# Copperleaf Restocking Agent — Decomposition & Planning Lab

## The problem, and why it needs decomposition + search

Twice a week (per `list_low_stock_items`), a Copperleaf Kitchen location has
several ingredients at or below `reorder_threshold`. Restocking all of them
is NOT a single tool call: several ingredients can be low at once, each has
candidate suppliers at different prices, some suppliers are unverified, and
`place_purchase_order` itself already enforces that any order over 80% of a
location's *remaining* monthly budget — or placed with an unverified
supplier — needs human confirmation (`mcp_server/tools_write.py`,
`safety_policies` #3). Committing to a full restock plan before seeing
whether the first order actually clears budget is a real, costly mistake:
it either blows the budget or spams the kitchen manager with confirmations
for orders that were never going to work. That's a planning problem, and
it's owned by a NEW agent (`agent/planning_agent/`), separate from and
never touching `agent/memory_rag_agent/`.

## Where every required concern lives

| Concern | File | What to look for |
|---|---|---|
| DAG construction + cycle check | `planning/dag.py` | `Plan.validate_dag`, enforced at construction, before any LLM call |
| Decomposition-first vs. dynamic (divergence point) | `planning/decomposition.py` vs. `planning/dynamic_decomposition.py` | Same `TaskKind`/tool contract, same real request type — see `planning_eval/test_cases.py::dag-02` for the actual divergence case |
| Routing PS vs. ToT vs. LATS | `planning/router.py` | A lookup on `task.kind`, decided upstream by the planner — not a judgment call in this file |
| Plan-and-Solve | `planning/plan_and_solve.py` | Single-pass restocking math (e.g. remaining budget) |
| Tree of Thoughts | `planning/tree_of_thoughts.py` | Ranking low-stock ingredients / weighing suppliers |
| LATS | `planning/lats.py` | Structured `PurchaseOrderCandidate` actions, UCT selection, branch reflection |
| Grounded environment (real, not random) | `planning/environment.py` | `RestockEnvironment.evaluate` calls the REAL `place_purchase_order` MCP tool and grades the actual server response |
| Self-Refine | `planning/self_refine.py` | Wired inline by `router.py` for every `"ps"` result |
| Reflexion (cross-trial memory) | `planning/reflexion.py` | Retries the whole `dynamic_decomposition()` run; graded by `_grade_trial`, which reads the real trace text |
| Fixed test suite + comparison harness | `planning_eval/test_cases.py`, `planning_eval/run_evaluation.py` | 8 tagged cases, one per required contrast |
| Agent entry point | `agent/planning_agent/main.py` | Opens the real MCP session, wires `Router` + `RestockEnvironment`, runs both decomposition methods |

## Why PS vs. ToT vs. LATS for this problem specifically

- **PS**: "how much budget is left" is a single deterministic calculation
  from numbers already gathered — branching would just waste calls.
- **ToT**: "which of 3 low-stock ingredients to prioritize under a tight
  budget" has several genuinely different orderings worth comparing before
  committing — that's exactly the shape ToT search is for.
- **LATS**: "place this purchase order" is a real action with a real
  pass/fail outcome from the server (budget/verification), and a failed
  attempt should produce a reflection grounded in the actual reason — that's
  exactly what LATS's environment-feedback + branch-reflection loop is for,
  and exactly what an ungrounded self-critique cannot do (it doesn't know
  the location's real remaining budget or a supplier's real verification
  status).

## Setup

Same environment as the rest of the repo:

```bash
pip install -r requirements.txt
pip install mcp langchain-mistralai python-dotenv networkx pydantic  # if not already covered
```

`.env` needs your LLM provider key (`MISTRAL_API_KEY` by default — see the
`TODO(team)` comments in `agent/planning_agent/main.py` and
`planning_eval/run_evaluation.py` if you're using a different provider
elsewhere in the repo; nothing in `planning/` itself hardcodes a provider).

## Run the agent

From the repo root:

```bash
python -m agent.planning_agent.main
```

This opens a real MCP session to `mcp_server/server.py`, runs
decomposition-first AND dynamic decomposition for the same restocking goal,
and routes every non-deterministic sub-task through the real
PS/ToT/LATS router — printing the DAG, the execution batches, every
sub-task's output, and the final result.

## Run the full evaluation / comparison table

```bash
python -m planning_eval.run_evaluation
```

Runs every method against every applicable case in
`planning_eval/test_cases.py` (fixed — do not edit once you've started
collecting numbers for the report) and writes one JSON trace per case, plus
`all_results.json`, into `planning_eval/results/`. Each trace already
carries `llm_calls`, `approx_tokens`, `latency_seconds`, and `task_success`
per method — build the README's comparison table straight from those files.

The one row you must add by hand: the **ungrounded** LATS contrast for
`ground-08-unverified-supplier-catch` (run the untouched toolkit fork's
original random `Environment` once against the same case) — deliberately
not wired into `run_evaluation.py` so the random evaluator can't
accidentally end up shipped as a default again.

## Demo checklist (for the required transcript/recording)

- [ ] `dag-02-mid-plan-budget-surprise`: show decomposition-first executing
      blindly after the first over-budget order vs. dynamic decomposition
      reacting to it.
- [ ] One sub-task solved by each of PS (`plan-03`), ToT (`plan-04`), LATS
      (`plan-05`).
- [ ] A Self-Refine revision (`refine-06`) — show the grounded issue it
      caught before the LLM critic even ran.
- [ ] A Reflexion run (`reflexion-07`) carrying a reflection across trials.
- [ ] `ground-08`: the grounded environment catching the unverified
      supplier, next to the ungrounded contrast run.
