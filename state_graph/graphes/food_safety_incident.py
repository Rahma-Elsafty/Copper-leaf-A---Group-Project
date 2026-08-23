"""
state_graph/graphs/food_safety_incident.py

Owning agent: "food_safety_incident_agent"

THE PROBLEM
-----------
`food_safety_incidents` already exists in the schema with a status column
(`open` -> `corrective_action_logged` -> `closed`) and a `summary` field the
schema comment says is "populated via sampling/createMessage" — i.e. the
original lab already knew this needed an LLM call, but never built the
workflow around it. Neither existing agent owns this: the Memory/RAG agent
only answers policy QUESTIONS, it never investigates or closes a real
incident; the Decomposition/Planning agent's DAG only ever plans a
restocking order.

An incident is not a single LLM call: closing one is an irreversible,
liability-affecting decision that must NOT be made by the model alone, the
corrective action often needs to be re-verified by a follow-up inspection
that happens on its own schedule (hours to days later), and a corrective
action that doesn't hold up on re-inspection has to go back to
investigation — a genuine cycle, not a straight line.

STATES
------
investigate -> hitl_review -> [apply_review_decision]
    -> (Wait) -> verify_corrective_action -- (fails re-inspection) --> investigate (cycle)
                                           \-- (passes) --> close -> Done

WHY IT NEEDS A STATE GRAPH
---------------------------
- Real cycle: a corrective action that fails re-inspection routes back to
  `investigate`, not to a dead end — the same node can run more than once
  for the same incident.
- Real external wait: `verify_corrective_action` waits on an actual
  re-inspection, which happens on the food safety officer's schedule.
- Real HITL: closing an incident is exactly the kind of irreversible,
  liability-relevant action this project's HITL guardrail calls out by
  name — the agent proposes, a food safety officer decides.
- Real failure a retry can't fix: a re-inspection that returns a result
  the graph can't parse (see `verify_corrective_action`) is a data
  problem, not a flaky call.

TWO LLM-CALL ADDITIONS
-----------------------
- RAG (`investigate`): retrieves the relevant `safety_policies` documents
  for the incident's type before proposing anything, via
  `state_graph.techniques.retrieve_grounding` — the same retrieval layer
  the platform's RAG document management screen (add/remove documents)
  actually affects, so an admin editing safety_policies content changes
  what this graph proposes on the very next incident.
- Tree of Thoughts (`investigate`): ranks 2-3 candidate corrective-action
  plans against the retrieved policy grounding via
  `state_graph.techniques.tree_of_thoughts_choice`, which calls the
  EXISTING `planning.tree_of_thoughts.tree_of_thoughts` directly (no
  reimplementation) — a genuine fit, since "which of a few candidate
  plans is best, scored against grounding" is exactly what that function
  already does generically.

HITL CONDITION
--------------
`hitl_review` ALWAYS fires before a `closed` status is ever written —
closing a food-safety incident is irreversible and liability-relevant by
definition, one of the guardrail conditions this project calls out
explicitly, so this is not threshold-gated like the purchase-order graph;
it is unconditional for this node.

FAILURE (TICKET) CONDITIONS
----------------------------
- `verify_corrective_action` raises NodeFailure if the re-inspection event
  payload doesn't contain a boolean `passed` field (a malformed external
  response the graph genuinely can't act on).
"""
from __future__ import annotations

from state_graph.engine import Done, Goto, HitlPause, NodeFailure, StateGraph, Wait
from state_graph.techniques import retrieve_grounding, tree_of_thoughts_choice

AGENT_NAME = "food_safety_incident_agent"
GRAPH_NAME = "food_safety_incident"

MAX_INVESTIGATION_CYCLES = 3


def investigate(state: dict):
    cycles = state.get("investigation_cycles", 0) + 1
    if cycles > MAX_INVESTIGATION_CYCLES:
        raise NodeFailure(
            f"Incident {state.get('incident_id')} failed re-inspection "
            f"{MAX_INVESTIGATION_CYCLES} times in a row — this needs a human "
            "to redesign the corrective action, not another automatic attempt."
        )

    incident_type = state.get("incident_type", "other")
    grounding = retrieve_grounding(query=incident_type, k=3)

    llm = state.get("_llm")  # injected by the caller when a real provider is configured
    if llm is not None:
        thoughts = tree_of_thoughts_choice(
            problem=(
                f"Incident type: {incident_type}. Propose a corrective action, "
                f"grounded in: {[g['text'][:200] for g in grounding]}"
            ),
            llm=llm,
        )
        candidate_plans = [{"plan": t.state, "score": t.score, "rationale": t.rationale} for t in thoughts]
    else:
        # deterministic fallback (no API key configured / demo / tests):
        # a single, clearly-labeled draft plan, still genuinely grounded in
        # whatever `retrieve_grounding` found — no ranking search happens
        # without an LLM, and that's stated plainly rather than faked.
        candidate_plans = [{
            "plan": f"Follow documented procedure for '{incident_type}' incidents.",
            "score": None,
            "rationale": "No LLM configured — single grounded draft, not a ranked search.",
        }]

    chosen_plan = candidate_plans[0]

    return Goto("hitl_review", {
        "grounding": grounding,
        "candidate_plans": candidate_plans,
        "chosen_plan": chosen_plan,
        "investigation_cycles": cycles,
    })


def hitl_review(state: dict):
    return HitlPause(
        resume_node="apply_review_decision",
        reason="Closing a food-safety incident is irreversible and liability-relevant; requires food safety officer sign-off.",
        payload={
            "incident_id": state.get("incident_id"),
            "incident_type": state.get("incident_type"),
            "chosen_plan": state.get("chosen_plan"),
            "alternatives": state.get("candidate_plans"),
            "grounding_sources": [g.get("source") for g in state.get("grounding", [])],
        },
    )


def apply_review_decision(state: dict):
    decision = state.get("hitl_decisions", {}).get("apply_review_decision")
    if decision is None:
        raise NodeFailure("apply_review_decision reached with no food safety officer decision present.")

    if not decision.get("approved"):
        return Goto("investigate", {
            "investigation_cycles": state.get("investigation_cycles", 0),
            "rejection_notes": decision.get("notes"),
        })

    if not state.get("_demo_mode"):
        from mcp_server.database import execute_update
        execute_update(
            "UPDATE food_safety_incidents SET status = 'corrective_action_logged', summary = ? WHERE incident_id = ?",
            (str(state.get("chosen_plan")), state.get("incident_id")),
        )

    return Wait(
        resume_node="verify_corrective_action",
        reason="Waiting for a follow-up inspection to confirm the corrective action actually held.",
        state_update={"approved_plan": state.get("chosen_plan"), "approval_notes": decision.get("notes")},
    )


def verify_corrective_action(state: dict):
    if "passed" not in state or not isinstance(state.get("passed"), bool):
        raise NodeFailure(
            "Re-inspection event did not include a usable pass/fail result "
            f"(got: {state.get('passed')!r})."
        )

    if not state["passed"]:
        return Goto("investigate", {
            "investigation_cycles": state.get("investigation_cycles", 0),
            "reinspection_notes": state.get("reinspection_notes"),
        })

    if not state.get("_demo_mode"):
        from mcp_server.database import execute_update
        execute_update(
            "UPDATE food_safety_incidents SET status = 'closed' WHERE incident_id = ?",
            (state.get("incident_id"),),
        )

    return Goto("close", {})


def close(state: dict):
    return Done({"closed": True})


def build_graph() -> StateGraph:
    g = StateGraph(GRAPH_NAME, start_node="investigate")
    g.add_node("investigate", investigate)
    g.add_node("hitl_review", hitl_review)
    g.add_node("apply_review_decision", apply_review_decision)
    g.add_node("verify_corrective_action", verify_corrective_action)
    g.add_node("close", close)
    return g
