"""
state_graph/demo_crash_recovery.py — reproducible crash-and-resume demo,
satisfying Final Project requirement #11.C literally: a real OS process is
started, progresses through several states, is killed with SIGKILL (not a
graceful shutdown), and a SECOND, independent process resumes the same run
from its last checkpoint, proving completed nodes are not re-executed.

Run it (from the repo root):

    python -m state_graph.demo_crash_recovery

It prints the run_id, which node it reached before being killed, and after
restart prints the resumed trace and the final state, so you can see the
proof directly in the terminal.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "db" / "demo_crash_recovery.db"

_WORKER_START = r"""
import sys, time
sys.path.insert(0, {repo!r})
from state_graph import db as sg_db
sg_db.set_db_path({db_path!r})
sg_db.ensure_schema()

from state_graph.graphs.purchase_order_fulfillment import build_graph

g = build_graph()
run_id = g.start({{
    "po_id": 4242,
    "ingredient_id": 1,
    "supplier_id": 1,
    "qty": 50,
    "unit_cost": 3.0,
    "requested_by": 2,
    "_demo_mode": True,   # graph nodes short-circuit real MCP writes in demo mode
}})
print("RUN_ID=" + run_id)
sys.stdout.flush()
# Simulate the delivery taking a while to arrive by sleeping right after
# the run parks in 'awaiting_delivery' (a genuine Wait state) — we kill
# the process during this sleep, well after checkpoints for the earlier
# nodes are already durably on disk.
time.sleep(30)
"""

_WORKER_RESUME = r"""
import sys
sys.path.insert(0, {repo!r})
from state_graph import db as sg_db
sg_db.set_db_path({db_path!r})

from state_graph import store
from state_graph.graphs.purchase_order_fulfillment import build_graph

run_id = {run_id!r}
g = build_graph()

run_before = store.get_run(run_id)
print(f"BEFORE RESUME: status={{run_before.status}} current_node={{run_before.current_node}}")

# The run is sitting in status='waiting' (parked at awaiting_delivery) —
# deliver the external event exactly the same way the platform's
# "supplier delivery webhook" endpoint would.
g.advance_waiting_run(run_id, "receive_delivery", {{"delivery_confirmed": True, "delivered_qty": 50}})

run_after = store.get_run(run_id)
print(f"AFTER RESUME: status={{run_after.status}} current_node={{run_after.current_node}}")

cp = store.latest_checkpoint(run_id)
print("FINAL STATE:", {{k: v for k, v in cp.state.items() if not k.startswith('_')}})

with store.connect() as conn:
    rows = conn.execute(
        "SELECT checkpoint_seq, completed_node FROM graph_checkpoints WHERE run_id=? ORDER BY checkpoint_seq",
        (run_id,),
    ).fetchall()
print("CHECKPOINT TRACE:", [r['completed_node'] for r in rows])
"""


def main() -> None:
    if DB_PATH.exists():
        DB_PATH.unlink()

    repo_root = str(Path(__file__).resolve().parent.parent)

    print("=== Phase 1: starting the run in a real subprocess ===")
    proc = subprocess.Popen(
        [sys.executable, "-c", _WORKER_START.format(repo=repo_root, db_path=str(DB_PATH))],
        stdout=subprocess.PIPE, text=True,
    )

    run_id = None
    # Wait for the worker to print its run_id (i.e. to have reached the
    # waiting state and durably checkpointed it) before we kill it.
    deadline = time.time() + 10
    while time.time() < deadline:
        line = proc.stdout.readline()
        if line.startswith("RUN_ID="):
            run_id = line.strip().split("=", 1)[1]
            break
    if run_id is None:
        raise RuntimeError("worker never reported a run_id")

    print(f"Run {run_id} reached 'awaiting_delivery' and checkpointed. Killing the process now (SIGKILL)...")
    time.sleep(0.5)  # make sure the checkpoint write's fsync has landed
    proc.kill()  # SIGKILL — no graceful shutdown, no chance to flush anything
    proc.wait()
    print(f"Process killed (exit could not run any cleanup code).\n")

    print("=== Phase 2: a SECOND, independent process resumes the run ===")
    resume_proc = subprocess.run(
        [sys.executable, "-c", _WORKER_RESUME.format(repo=repo_root, db_path=str(DB_PATH), run_id=run_id)],
        capture_output=True, text=True,
    )
    print(resume_proc.stdout)
    if resume_proc.returncode != 0:
        print(resume_proc.stderr, file=sys.stderr)
        raise SystemExit(resume_proc.returncode)


if __name__ == "__main__":
    main()
