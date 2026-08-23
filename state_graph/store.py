"""
state_graph/store.py — the persistence API every graph node, test, and
platform endpoint goes through. Nothing outside this module and
state_graph/db.py talks to the state-graph SQLite file directly — that's
what keeps "where checkpoints/HITL/tickets are read and written" locatable
in exactly one place, per the assignment's "locatable concerns" requirement.
"""
from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Optional

from state_graph import db


@dataclass
class Run:
    run_id: str
    graph_name: str
    agent_name: Optional[str]
    status: str
    current_node: Optional[str]


@dataclass
class Checkpoint:
    run_id: str
    checkpoint_seq: int
    completed_node: str
    state: dict


@contextmanager
def connect():
    """Context-managed connection: commits on clean exit, always closes.
    Used directly by demo_crash_recovery.py to read the raw checkpoint
    trace, and internally by every function below."""
    conn = db.connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------

def create_run(run_id: str, graph_name: str, agent_name: Optional[str], current_node: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO graph_runs (run_id, graph_name, agent_name, status, current_node) "
            "VALUES (?, ?, ?, 'running', ?)",
            (run_id, graph_name, agent_name, current_node),
        )


def update_run_status(run_id: str, status: str, current_node: Optional[str]) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE graph_runs SET status = ?, current_node = ?, updated_at = datetime('now') WHERE run_id = ?",
            (status, current_node, run_id),
        )


def get_run(run_id: str) -> Run:
    with connect() as conn:
        row = conn.execute("SELECT * FROM graph_runs WHERE run_id = ?", (run_id,)).fetchone()
    if row is None:
        raise KeyError(f"No such run: {run_id}")
    return Run(row["run_id"], row["graph_name"], row["agent_name"], row["status"], row["current_node"])


def list_runs(status: Optional[str] = None) -> list[dict]:
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM graph_runs WHERE status = ? ORDER BY updated_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM graph_runs ORDER BY updated_at DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Checkpoints — written after EVERY meaningful node transition, not just
# at the end of a run and not just on failure. This is what
# demo_crash_recovery.py's kill-and-resume proves.
# ---------------------------------------------------------------------

def write_checkpoint(run_id: str, completed_node: str, state: dict) -> int:
    serializable_state = {k: v for k, v in state.items() if k != "_llm"}
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(checkpoint_seq), 0) AS m FROM graph_checkpoints WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        next_seq = row["m"] + 1
        conn.execute(
            "INSERT INTO graph_checkpoints (run_id, checkpoint_seq, completed_node, state_json) VALUES (?, ?, ?, ?)",
            (run_id, next_seq, completed_node, json.dumps(serializable_state, default=str)),
        )
    return next_seq


def latest_checkpoint(run_id: str) -> Checkpoint:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM graph_checkpoints WHERE run_id = ? ORDER BY checkpoint_seq DESC LIMIT 1",
            (run_id,),
        ).fetchone()
    if row is None:
        raise KeyError(f"No checkpoints for run: {run_id}")
    return Checkpoint(row["run_id"], row["checkpoint_seq"], row["completed_node"], json.loads(row["state_json"]))


def list_checkpoints(run_id: str) -> list[Checkpoint]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM graph_checkpoints WHERE run_id = ? ORDER BY checkpoint_seq", (run_id,)
        ).fetchall()
    return [
        Checkpoint(r["run_id"], r["checkpoint_seq"], r["completed_node"], json.loads(r["state_json"]))
        for r in rows
    ]


# ---------------------------------------------------------------------
# HITL tasks — an EXPECTED pause for a decision the agent isn't allowed
# to make alone. Distinct table, distinct workflow from failure tickets.
# ---------------------------------------------------------------------

def create_hitl_task(run_id: str, resume_node: str, reason: str, payload: dict) -> str:
    task_id = new_id("hitl")
    with connect() as conn:
        conn.execute(
            "INSERT INTO hitl_tasks (task_id, run_id, resume_node, reason, payload_json, status) "
            "VALUES (?, ?, ?, ?, ?, 'pending')",
            (task_id, run_id, resume_node, reason, json.dumps(payload, default=str)),
        )
    return task_id


def list_hitl_tasks(status: Optional[str] = "pending") -> list[dict]:
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM hitl_tasks WHERE status = ? ORDER BY created_at", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM hitl_tasks ORDER BY created_at").fetchall()
    return [dict(r) for r in rows]


def get_hitl_task(task_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM hitl_tasks WHERE task_id = ?", (task_id,)).fetchone()
    if row is None:
        raise KeyError(f"No such HITL task: {task_id}")
    return dict(row)


def resolve_hitl_task(task_id: str, status: str, decision: dict, resolved_by: str) -> dict:
    """status is the ADMIN's verdict ('approved'/'rejected'), not the
    graph run's status. Returns the updated row so a caller can read back
    decision_json immediately (see every graph test:
    `resolved = store.resolve_hitl_task(...); g.resolve_hitl_and_resume(
    run_id, node, json.loads(resolved["decision_json"]))`)."""
    if status not in ("approved", "rejected"):
        raise ValueError("status must be 'approved' or 'rejected'")
    decision_json = json.dumps(decision, default=str)
    with connect() as conn:
        conn.execute(
            "UPDATE hitl_tasks SET status = ?, decision_json = ?, resolved_by = ?, resolved_at = datetime('now') "
            "WHERE task_id = ?",
            (status, decision_json, resolved_by, task_id),
        )
        row = conn.execute("SELECT * FROM hitl_tasks WHERE task_id = ?", (task_id,)).fetchone()
    return dict(row)


# ---------------------------------------------------------------------
# Failure tickets — UNPLANNED: a tool call errored, a schema validation
# failed, an external event the graph can't act on. Never manually
# inserted for a demo — only ever created from a real NodeFailure the
# engine caught (see engine.py's _run_node).
# ---------------------------------------------------------------------

def create_failure_ticket(run_id: str, node: str, error_message: str, checkpoint_seq: int) -> str:
    ticket_id = new_id("ticket")
    with connect() as conn:
        conn.execute(
            "INSERT INTO failure_tickets (ticket_id, run_id, node, error_message, status, checkpoint_seq) "
            "VALUES (?, ?, ?, ?, 'open', ?)",
            (ticket_id, run_id, node, error_message, checkpoint_seq),
        )
    return ticket_id


def list_failure_tickets(status: Optional[str] = None) -> list[dict]:
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM failure_tickets WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM failure_tickets ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


def get_failure_ticket(ticket_id: str) -> dict:
    with connect() as conn:
        row = conn.execute("SELECT * FROM failure_tickets WHERE ticket_id = ?", (ticket_id,)).fetchone()
    if row is None:
        raise KeyError(f"No such ticket: {ticket_id}")
    return dict(row)


def update_ticket_status(ticket_id: str, status: str, resolution_notes: Optional[str] = None) -> None:
    if status not in ("open", "investigating", "resolved"):
        raise ValueError("status must be open | investigating | resolved")
    with connect() as conn:
        if status == "resolved":
            conn.execute(
                "UPDATE failure_tickets SET status = ?, resolved_at = datetime('now'), "
                "resolution_notes = COALESCE(?, resolution_notes) WHERE ticket_id = ?",
                (status, resolution_notes, ticket_id),
            )
        else:
            conn.execute(
                "UPDATE failure_tickets SET status = ?, resolution_notes = COALESCE(?, resolution_notes) "
                "WHERE ticket_id = ?",
                (status, resolution_notes, ticket_id),
            )


# ---------------------------------------------------------------------
# Agent <-> MCP tool permissions. Read by BOTH state_graph/mcp_bridge.py
# (in-process calls from graph nodes) and mcp_server/server.py's stdio
# on_call_tool dispatch, so an admin disabling a tool via the platform
# blocks it identically on both paths — one source of truth, no second
# permission system.
# ---------------------------------------------------------------------

def is_tool_allowed(agent_name: str, tool_name: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT allowed FROM agent_tool_permissions WHERE agent_name = ? AND tool_name = ?",
            (agent_name, tool_name),
        ).fetchone()
    if row is None:
        return True  # default-allow until an admin has ever touched this pair
    return bool(row["allowed"])


def set_tool_allowed(agent_name: str, tool_name: str, allowed: bool) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO agent_tool_permissions (agent_name, tool_name, allowed) VALUES (?, ?, ?) "
            "ON CONFLICT(agent_name, tool_name) DO UPDATE SET allowed = excluded.allowed",
            (agent_name, tool_name, int(allowed)),
        )


def list_tool_permissions(agent_name: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT tool_name, allowed FROM agent_tool_permissions WHERE agent_name = ?", (agent_name,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# RAG documents — the admin-managed store that state_graph.techniques.
# retrieve_grounding's SQL fallback path reads, and that the platform's
# RAG document-management screen writes into directly.
# ---------------------------------------------------------------------

def add_rag_document(title: str, text: str, added_by: Optional[str] = None) -> str:
    doc_id = new_id("doc")
    with connect() as conn:
        conn.execute(
            "INSERT INTO rag_documents (doc_id, title, text, added_by) VALUES (?, ?, ?, ?)",
            (doc_id, title, text, added_by),
        )
    return doc_id


def remove_rag_document(doc_id: str) -> None:
    with connect() as conn:
        conn.execute("DELETE FROM rag_documents WHERE doc_id = ?", (doc_id,))


def list_rag_documents() -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM rag_documents ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------
# Known agents — for the admin platform's "agents & tools" screen. An
# agent becomes "known" the moment it EITHER has an explicit tool
# permission row OR has ever started a graph run — this is deliberately
# not a hardcoded list, since new state-graph agents should show up on
# the admin screen the moment they run, with no separate registration
# step to keep in sync.
# ---------------------------------------------------------------------

def list_known_agents() -> list[str]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT agent_name AS name FROM agent_tool_permissions
            UNION
            SELECT DISTINCT agent_name AS name FROM graph_runs WHERE agent_name IS NOT NULL
            ORDER BY name
            """
        ).fetchall()
    return [r["name"] for r in rows]
