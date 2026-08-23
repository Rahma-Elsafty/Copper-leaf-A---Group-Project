"""
state_graph/graphs/supplier_onboarding.py

Owning agent: "supplier_onboarding_agent"

THE PROBLEM
-----------
`suppliers.verified` gates whether a supplier can be used without tripping
the purchase-order HITL condition (see purchase_order_fulfillment.py and
mcp_server/tools_write.py::place_purchase_order), and
`mark_supplier_verified` already exists as an MCP tool — but nothing in
the system currently decides WHEN it's safe to call that tool. Today
that's a silent, unaudited human action outside the product entirely.

Onboarding a new supplier genuinely spans time: compliance checks against
policy documents, a kitchen manager's sign-off, and then waiting on the
supplier to actually return a signed agreement — which can take days and
can simply never come back, at which point the onboarding has to fail
cleanly rather than leave a half-verified supplier hanging forever.

STATES
------
compliance_check -> hitl_approval -> [apply_onboarding_decision]
    -> (Wait) -> confirm_agreement -> mark_verified -> Done

WHY IT NEEDS A STATE GRAPH
---------------------------
- Genuine external dependency: the transition out of `awaiting_agreement`
  depends on the supplier signing and returning a document, not on
  anything the model controls.
- Genuine wait that may never resolve: an unsigned agreement after the
  configured window is swept the same way an undelivered order is (see
  `platform/backend.py`'s timeout sweep) and becomes a ticket, not an
  infinite hang.
- Genuine irreversible action requiring sign-off: marking a supplier
  verified changes every future purchase order's HITL exposure for that
  supplier — exactly the kind of consequential, hard-to-undo action this
  project's HITL guardrail targets.

TWO LLM-CALL ADDITIONS
-----------------------
- RAG (`compliance_check`): retrieves the relevant vetting/food-safety
  policy documents (same `retrieve_grounding` / admin-managed document
  store as the food-safety graph) to ground what the compliance summary
  actually checks the candidate supplier against, instead of the model
  inventing criteria.
- Constrained ReAct (`compliance_check`): the ONLY tool this node is
  allowed to call is `get_supplier` (read-only lookup of what's already on
  file) — it explicitly may NOT call `mark_supplier_verified` itself; that
  write only ever happens in `mark_verified`, after both the HITL sign-off
  and the external signed-agreement wait have actually completed. This is
  the constrained part earning its place: the whitelist is what keeps a
  verification write from ever happening on the strength of an LLM's own
  say-so.

HITL CONDITION
--------------
`hitl_approval` always fires — marking a supplier verified is exactly the
"action that contradicts a stated policy if done wrong" / "irreversible
enough to matter" case from the assignment's guardrail list; a kitchen
manager must sign off before onboarding proceeds any further.

FAILURE (TICKET) CONDITIONS
----------------------------
- `confirm_agreement` raises NodeFailure if the run is swept as timed-out
  (the supplier never returned a signed agreement).
- `compliance_check` raises NodeFailure if the candidate supplier can't be
  found at all (nothing to check).
"""
from __future__ import annotations

from state_graph.engine import Done, Goto, HitlPause, NodeFailure, StateGraph, Wait
from state_graph.mcp_bridge import make_call_tool
from state_graph.techniques import constrained_react, retrieve_grounding

AGENT_NAME = "supplier_onboarding_agent"
GRAPH_NAME = "supplier_onboarding"


def compliance_check(state: dict):
    grounding = retrieve_grounding(query="supplier vetting compliance", k=3)

    if state.get("_demo_mode"):
        lookup = [{"step": 1, "tool": "get_supplier", "arguments": {"supplier_id": state.get("supplier_id")},
                   "result": {"supplier_id": state.get("supplier_id"), "verified": False, "demo": True}}]
    else:
        call_tool = make_call_tool(AGENT_NAME)
        lookup = constrained_react(
            goal=f"Look up everything on file for candidate supplier {state.get('supplier_id')}",
            allowed_tools=["get_supplier"],  # deliberately NOT mark_supplier_verified
            call_tool=call_tool,
            steps=[{"step": 1, "item": {"supplier_id": state.get("supplier_id")}, "instruction": "Look up the supplier record."}],
        )
        if not lookup or lookup[0]["result"] is None:
            raise NodeFailure(f"Supplier {state.get('supplier_id')} not found — nothing to check.")

    return Goto("hitl_approval", {"grounding": grounding, "supplier_lookup": lookup})


def hitl_approval(state: dict):
    return HitlPause(
        resume_node="apply_onboarding_decision",
        reason="Marking a supplier verified changes every future purchase order's approval exposure for them; requires kitchen manager sign-off.",
        payload={
            "supplier_id": state.get("supplier_id"),
            "supplier_lookup": state.get("supplier_lookup"),
            "grounding_sources": [g.get("source") for g in state.get("grounding", [])],
        },
    )


def apply_onboarding_decision(state: dict):
    decision = state.get("hitl_decisions", {}).get("apply_onboarding_decision")
    if decision is None:
        raise NodeFailure("apply_onboarding_decision reached with no kitchen manager decision present.")

    if not decision.get("approved"):
        return Done({"onboarded": False, "reason": decision.get("notes", "Rejected by kitchen manager.")})

    return Wait(
        resume_node="confirm_agreement",
        reason="Waiting for the supplier to return a signed agreement.",
        state_update={"approval_notes": decision.get("notes")},
    )


def confirm_agreement(state: dict):
    if state.get("timed_out"):
        raise NodeFailure(
            f"Supplier {state.get('supplier_id')} never returned a signed agreement within the "
            "expected window — a retry cannot make them sign it."
        )
    if not state.get("agreement_signed"):
        raise NodeFailure("confirm_agreement reached without a signed-agreement confirmation event.")
    return Goto("mark_verified", {})


def mark_verified(state: dict):
    if state.get("_demo_mode"):
        result = {"verified": True, "demo": True}
    else:
        call_tool = make_call_tool(AGENT_NAME)
        result = call_tool("mark_supplier_verified", {"supplier_id": state.get("supplier_id")})
    return Done({"onboarded": True, "verification_result": result})


def build_graph() -> StateGraph:
    g = StateGraph(GRAPH_NAME, start_node="compliance_check")
    g.add_node("compliance_check", compliance_check)
    g.add_node("hitl_approval", hitl_approval)
    g.add_node("apply_onboarding_decision", apply_onboarding_decision)
    g.add_node("confirm_agreement", confirm_agreement)
    g.add_node("mark_verified", mark_verified)
    return g
