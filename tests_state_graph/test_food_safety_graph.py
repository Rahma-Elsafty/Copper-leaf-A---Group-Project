import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from graph_conftest import business_db  # noqa: E402,F401

from state_graph import store
from state_graph.graphs.food_safety_incident import build_graph


def test_incident_always_pauses_for_hitl_before_closing(business_db):
    g = build_graph()
    run_id = g.start({"incident_id": 1, "incident_type": "temperature_breach"})

    run = store.get_run(run_id)
    assert run.status == "hitl_paused"

    task = store.list_hitl_tasks(status="pending")[0]
    assert task["run_id"] == run_id
    payload = json.loads(task["payload_json"])
    assert payload["incident_id"] == 1
    # grounded in the seeded safety_policies row via the SQL fallback path
    assert "chosen_plan" in payload


def test_reinspection_failure_cycles_back_to_investigate_not_a_dead_end(business_db):
    g = build_graph()
    run_id = g.start({"incident_id": 1, "incident_type": "temperature_breach"})
    task = store.list_hitl_tasks(status="pending")[0]

    resolved = store.resolve_hitl_task(task["task_id"], "approved", {"approved": True, "notes": "Proceed."}, "staff_3")
    g.resolve_hitl_and_resume(run_id, "apply_review_decision", json.loads(resolved["decision_json"]))

    run = store.get_run(run_id)
    assert run.status == "waiting"
    assert run.current_node == "verify_corrective_action"

    # re-inspection FAILS -> must cycle back to investigate, not fail out
    g.advance_waiting_run(run_id, "verify_corrective_action", {"passed": False, "reinspection_notes": "Still too warm."})

    run = store.get_run(run_id)
    assert run.status == "hitl_paused"  # investigate ran again and re-paused for review
    cp = store.latest_checkpoint(run_id)
    assert cp.state["investigation_cycles"] == 2  # genuinely visited investigate twice


def test_reinspection_pass_closes_the_incident(business_db):
    g = build_graph()
    run_id = g.start({"incident_id": 1, "incident_type": "temperature_breach"})
    task = store.list_hitl_tasks(status="pending")[0]
    resolved = store.resolve_hitl_task(task["task_id"], "approved", {"approved": True}, "staff_3")
    g.resolve_hitl_and_resume(run_id, "apply_review_decision", json.loads(resolved["decision_json"]))

    g.advance_waiting_run(run_id, "verify_corrective_action", {"passed": True})

    run = store.get_run(run_id)
    assert run.status == "completed"
    cp = store.latest_checkpoint(run_id)
    assert cp.state["closed"] is True


def test_malformed_reinspection_result_opens_a_ticket(business_db):
    g = build_graph()
    run_id = g.start({"incident_id": 1, "incident_type": "temperature_breach"})
    task = store.list_hitl_tasks(status="pending")[0]
    resolved = store.resolve_hitl_task(task["task_id"], "approved", {"approved": True}, "staff_3")
    g.resolve_hitl_and_resume(run_id, "apply_review_decision", json.loads(resolved["decision_json"]))

    # external system returns something the graph can't act on
    g.advance_waiting_run(run_id, "verify_corrective_action", {"passed": "unclear"})

    run = store.get_run(run_id)
    assert run.status == "failed"
    tickets = store.list_failure_tickets(status="open")
    assert len(tickets) == 1
