import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_conftest import business_db  # noqa: E402,F401

from state_graph import store
from state_graph.graphs.supplier_onboarding import build_graph


def test_full_onboarding_happy_path(business_db):
    g = build_graph()
    run_id = g.start({"supplier_id": 2})  # the unverified seed supplier

    run = store.get_run(run_id)
    assert run.status == "hitl_paused"
    task = store.list_hitl_tasks(status="pending")[0]

    resolved = store.resolve_hitl_task(task["task_id"], "approved", {"approved": True}, "staff_2")
    g.resolve_hitl_and_resume(run_id, "apply_onboarding_decision", json.loads(resolved["decision_json"]))

    run = store.get_run(run_id)
    assert run.status == "waiting"
    assert run.current_node == "confirm_agreement"

    g.advance_waiting_run(run_id, "confirm_agreement", {"agreement_signed": True})

    run = store.get_run(run_id)
    assert run.status == "completed"
    cp = store.latest_checkpoint(run_id)
    assert cp.state["onboarded"] is True

    # the actual DB write happened for real, through mark_supplier_verified
    from mcp_server.database import execute_query
    row = execute_query("SELECT verified FROM suppliers WHERE supplier_id = 2")[0]
    assert row["verified"] == 1


def test_kitchen_manager_can_reject_without_ever_writing_verified(business_db):
    g = build_graph()
    run_id = g.start({"supplier_id": 2})
    task = store.list_hitl_tasks(status="pending")[0]

    resolved = store.resolve_hitl_task(task["task_id"], "rejected", {"approved": False, "notes": "Missing references."}, "staff_2")
    g.resolve_hitl_and_resume(run_id, "apply_onboarding_decision", json.loads(resolved["decision_json"]))

    run = store.get_run(run_id)
    assert run.status == "completed"
    cp = store.latest_checkpoint(run_id)
    assert cp.state["onboarded"] is False

    from mcp_server.database import execute_query
    row = execute_query("SELECT verified FROM suppliers WHERE supplier_id = 2")[0]
    assert row["verified"] == 0  # never touched


def test_supplier_that_never_signs_becomes_a_ticket_not_an_infinite_wait(business_db):
    g = build_graph()
    run_id = g.start({"supplier_id": 2})
    task = store.list_hitl_tasks(status="pending")[0]
    resolved = store.resolve_hitl_task(task["task_id"], "approved", {"approved": True}, "staff_2")
    g.resolve_hitl_and_resume(run_id, "apply_onboarding_decision", json.loads(resolved["decision_json"]))

    g.advance_waiting_run(run_id, "confirm_agreement", {"timed_out": True})

    run = store.get_run(run_id)
    assert run.status == "failed"
    tickets = store.list_failure_tickets(status="open")
    assert len(tickets) == 1
    assert "never returned" in tickets[0]["error_message"]
