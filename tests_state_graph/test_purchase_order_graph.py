import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_conftest import business_db  # noqa: E402,F401  (fixture import)

from state_graph import store
from state_graph.graphs.purchase_order_fulfillment import build_graph


def test_verified_low_cost_order_skips_hitl_and_completes(business_db):
    g = build_graph()
    run_id = g.start({
        "po_id": 100, "ingredient_id": 1, "supplier_id": 1,
        "qty": 50, "unit_cost": 3.0, "requested_by": 2, "stock_id": 1,
    })

    run = store.get_run(run_id)
    assert run.status == "waiting"
    assert run.current_node == "receive_delivery"
    assert store.list_hitl_tasks(status="pending") == []  # verified supplier, cheap order -> no HITL

    g.advance_waiting_run(run_id, "receive_delivery", {"delivery_confirmed": True, "delivered_qty": 50})

    run = store.get_run(run_id)
    assert run.status == "completed"
    cp = store.latest_checkpoint(run_id)
    assert cp.state["fulfilled"] is True


def test_unverified_supplier_triggers_real_hitl_pause(business_db):
    g = build_graph()
    run_id = g.start({
        "po_id": 101, "ingredient_id": 1, "supplier_id": 2,  # unverified supplier
        "qty": 500, "unit_cost": 8.4, "requested_by": 2, "stock_id": 1,
    })

    run = store.get_run(run_id)
    assert run.status == "hitl_paused"

    tasks = store.list_hitl_tasks(status="pending")
    assert len(tasks) == 1
    assert "Supplier is not verified." in tasks[0]["reason"]

    # admin rejects it
    resolved = store.resolve_hitl_task(tasks[0]["task_id"], "rejected", {"approved": False, "notes": "Not yet."}, "staff_2")
    import json
    g.resolve_hitl_and_resume(run_id, "apply_approval_decision", json.loads(resolved["decision_json"]))

    run = store.get_run(run_id)
    assert run.status == "completed"
    cp = store.latest_checkpoint(run_id)
    assert cp.state["cancelled"] is True


def test_delivery_quantity_mismatch_opens_a_ticket_not_a_silent_success(business_db):
    g = build_graph()
    run_id = g.start({
        "po_id": 100, "ingredient_id": 1, "supplier_id": 1,
        "qty": 50, "unit_cost": 3.0, "requested_by": 2, "stock_id": 1,
    })

    # delivered way less than ordered — a fact retrying can't fix
    g.advance_waiting_run(run_id, "receive_delivery", {"delivery_confirmed": True, "delivered_qty": 10})

    run = store.get_run(run_id)
    assert run.status == "failed"
    tickets = store.list_failure_tickets(status="open")
    assert len(tickets) == 1
    assert "Delivered quantity" in tickets[0]["error_message"]


def test_timeout_sweep_opens_a_ticket_for_a_delivery_that_never_arrives(business_db):
    g = build_graph()
    run_id = g.start({
        "po_id": 100, "ingredient_id": 1, "supplier_id": 1,
        "qty": 50, "unit_cost": 3.0, "requested_by": 2, "stock_id": 1,
    })

    g.advance_waiting_run(run_id, "receive_delivery", {"timed_out": True})

    run = store.get_run(run_id)
    assert run.status == "failed"
    tickets = store.list_failure_tickets(status="open")
    assert "never" in tickets[0]["error_message"] or "did not confirm" in tickets[0]["error_message"]
