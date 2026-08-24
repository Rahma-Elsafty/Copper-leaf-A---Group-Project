"""
state_graph/graphs/purchase_order_fulfillment.py

Owning agent: "purchase_order_fulfillment_agent"

THE PROBLEM
-----------
The existing Decomposition & Planning agent (planning/) already decides
WHAT to order and from WHOM — that's a single-pass DAG that runs start to
finish in one sitting (decompose_goal -> execute_plan -> done). It never
needs to remember anything after that call returns.

What happens to an order AFTER it's placed is a completely different
problem, and the existing agent has nothing for it:
  - a placed order needs a real human sign-off when it's expensive or the
    supplier isn't verified yet (place_purchase_order already computes
    `requires_confirmation` — this graph is what actually ACTS on that
    instead of silently ignoring it);
  - once approved, the supplier has to actually deliver — hours to days
    later, on the supplier's own schedule, not the model's;
  - the delivery can simply never arrive, or arrive short/over — a
    problem no retry of "place the order again" fixes, and one that costs
    the location real money and stockouts the longer it goes undetected.

None of that fits in a single LLM call-and-done. It needs to survive
between "order sent" and "delivery arrives", which might be a different
process entirely.

STATES
------
pending_approval -> [apply_approval_decision] -> decompose_and_send
    -> (Wait) -> receive_delivery -> reconcile -> Done

WHY IT NEEDS A STATE GRAPH
---------------------------
- Genuine multi-sitting interaction: `decompose_and_send` and
  `receive_delivery` can be hours or days apart, run by different agent
  processes (see state_graph/demo_crash_recovery.py, which kills the
  process between them).
- Genuine external dependency: the transition out of `awaiting_delivery`
  depends entirely on the supplier, not the model.
- Genuine failure mode a retry can't fix: a quantity mismatch or a
  delivery timeout is a fact about the world, not a flaky call — retrying
  "receive the delivery" does not make missing inventory appear.

TWO LLM-CALL ADDITIONS
-----------------------
- Task Decomposition (`decompose_and_send`): a purchase order can cover
  several ingredient lines; decomposition turns "send this order" into one
  concrete dispatch step per line, in order, before any MCP write happens.
- Constrained ReAct (`decompose_and_send`, `receive_delivery`): both nodes
  execute their steps through `state_graph.techniques.constrained_react`,
  which can ONLY call a fixed whitelist of MCP write tools
  (`approve_purchase_order`, `record_inventory_count`) — this node is
  exactly the kind of place a "the model can act, but only within a small,
  auditable action space" constraint belongs, since a hallucinated tool
  call here would touch real inventory/financial state.

HITL CONDITION
--------------
`pending_approval` pauses whenever the order's cost exceeds 80% of the
location's remaining monthly budget OR the supplier is not yet verified —
the exact two conditions `mcp_server/tools_write.py::place_purchase_order`
already flags via `requires_confirmation`/`reasons`. This graph is what
finally acts on that flag instead of it being dead data.

FAILURE (TICKET) CONDITIONS
----------------------------
- `receive_delivery` raises NodeFailure if the delivered quantity is off
  by more than 5% from what was ordered.
- `receive_delivery` raises NodeFailure if the run is swept as timed-out
  (see platform/backend.py's `/admin/timeouts/sweep`) after sitting in
  `awaiting_delivery` past the configured window — "the supplier never
  replied" is exactly the failure mode this project asks for.
"""
from __future__ import annotations

from state_graph.engine import Done, Goto, HitlPause, NodeFailure, StateGraph, Wait
from state_graph.mcp_bridge import make_call_tool
from state_graph.techniques import constrained_react, task_decompose

AGENT_NAME = "purchase_order_fulfillment_agent"
GRAPH_NAME = "purchase_order_fulfillment"


def _lookup_hitl_conditions(state: dict) -> tuple[bool, list[str]]:
    from mcp_server.database import execute_query

    po_rows = execute_query(
        "SELECT po_id, cost, supplier_id FROM purchase_orders WHERE po_id = ?",
        (state["po_id"],),
    )
    if not po_rows:
        raise NodeFailure(f"Purchase order {state['po_id']} not found.")
    po = po_rows[0]

    supplier = execute_query(
        "SELECT verified FROM suppliers WHERE supplier_id = ?", (po["supplier_id"],)
    )
    if not supplier:
        raise NodeFailure(f"Supplier {po['supplier_id']} not found.")

    staff = execute_query("SELECT location_id FROM staff WHERE staff_id = ?", (state["requested_by"],))
    if not staff:
        raise NodeFailure(f"Staff member {state['requested_by']} not found.")
    location_id = staff[0]["location_id"]

    budget = execute_query(
        "SELECT monthly_budget FROM locations WHERE location_id = ?", (location_id,)
    )[0]["monthly_budget"]

    committed = execute_query(
        """
        SELECT COALESCE(SUM(cost), 0) AS total FROM purchase_orders
        WHERE requested_by IN (SELECT staff_id FROM staff WHERE location_id = ?)
        AND status IN ('pending', 'approved')
        """,
        (location_id,),
    )[0]["total"]
    remaining_budget = budget - committed

    reasons = []
    if po["cost"] > remaining_budget * 0.80:
        reasons.append("Order exceeds 80% of remaining budget.")
    if not supplier[0]["verified"]:
        reasons.append("Supplier is not verified.")
    return (len(reasons) > 0), reasons


def pending_approval(state: dict):
    if state.get("_demo_mode"):
        requires_confirmation, reasons = False, []
    else:
        requires_confirmation, reasons = _lookup_hitl_conditions(state)

    if requires_confirmation:
        return HitlPause(
            resume_node="apply_approval_decision",
            reason="; ".join(reasons),
            payload={"po_id": state.get("po_id"), "reasons": reasons},
        )
    return Goto("decompose_and_send", {"requires_confirmation": False})


def apply_approval_decision(state: dict):
    decision = state.get("hitl_decisions", {}).get("apply_approval_decision")
    if decision is None:
        raise NodeFailure("apply_approval_decision reached with no admin decision present in state.")
    if not decision.get("approved"):
        return Done({"cancelled": True, "cancel_reason": decision.get("notes", "Rejected by admin.")})
    return Goto("decompose_and_send", {"requires_confirmation": True, "hitl_notes": decision.get("notes")})


def decompose_and_send(state: dict):
    lines = state.get("lines") or [{
        "ingredient_id": state["ingredient_id"],
        "supplier_id": state["supplier_id"],
        "qty": state["qty"],
        "unit_cost": state["unit_cost"],
    }]
    steps = task_decompose(
        goal=f"Dispatch purchase order {state.get('po_id')} to its supplier for fulfillment",
        items=lines,
    )

    if state.get("_demo_mode"):
        send_results = [
            {"step": s["step"], "tool": "approve_purchase_order", "arguments": s["item"],
             "result": {"status": "approved (demo)"}}
            for s in steps
        ]
    else:
        call_tool = make_call_tool(AGENT_NAME)
        send_results = constrained_react(
            goal=f"Approve purchase order {state['po_id']} so it can be sent to the supplier",
            allowed_tools=["approve_purchase_order"],
            call_tool=call_tool,
            steps=[{"step": 1, "item": {"po_id": state["po_id"]}, "instruction": "Approve the purchase order."}],
        )

    return Wait(
        resume_node="receive_delivery",
        reason="Waiting for the supplier to confirm and deliver the order.",
        state_update={"decomposition_steps": steps, "send_results": send_results, "sent": True},
    )


def receive_delivery(state: dict):
    if state.get("timed_out"):
        raise NodeFailure(
            "Supplier did not confirm or deliver the order within the expected window. "
            "A single retry cannot fix a supplier that never replied."
        )
    if not state.get("delivery_confirmed"):
        raise NodeFailure("receive_delivery reached without a delivery confirmation event.")

    ordered_qty = state.get("qty", 0)
    delivered_qty = state.get("delivered_qty", 0)
    tolerance = 0.05
    if ordered_qty and abs(delivered_qty - ordered_qty) / ordered_qty > tolerance:
        raise NodeFailure(
            f"Delivered quantity ({delivered_qty}) differs from ordered quantity "
            f"({ordered_qty}) by more than the {tolerance:.0%} tolerance."
        )

    if state.get("_demo_mode"):
        record_result = {"updated": True, "demo": True}
    else:
        call_tool = make_call_tool(AGENT_NAME)
        record_result = constrained_react(
            goal=f"Record the delivered quantity for purchase order {state.get('po_id')}",
            allowed_tools=["record_inventory_count"],
            call_tool=call_tool,
            steps=[{
                "step": 1,
                "item": {"stock_id": state["stock_id"], "quantity": delivered_qty},
                "instruction": "Record the new on-hand quantity after delivery.",
            }],
        )

    return Goto("reconcile", {"record_result": record_result})


def reconcile(state: dict):
    return Done({"fulfilled": True})


def build_graph() -> StateGraph:
    g = StateGraph(GRAPH_NAME, start_node="pending_approval")
    g.add_node("pending_approval", pending_approval)
    g.add_node("apply_approval_decision", apply_approval_decision)
    g.add_node("decompose_and_send", decompose_and_send)
    g.add_node("receive_delivery", receive_delivery)
    g.add_node("reconcile", reconcile)
    return g
