"""
state_graph/db.py — SQLite connection management for the state-graph
persistence layer (runs, checkpoints, HITL tasks, failure tickets, and
per-agent tool permissions).

Deliberately its OWN small database file, not the main db/copperleaf.db
schema (db/schema.sql) that mcp_server/database.py owns — the state graph
tracks a different kind of thing (long-lived run/graph execution state)
than copperleaf.db does (business data: suppliers, purchase_orders,
food_safety_incidents, etc). Graph nodes still read/write copperleaf.db
directly for real business effects (see mcp_bridge.py / mcp_server.database)
— this module only persists the GRAPH's own state, which is what makes
crash-and-resume (demo_crash_recovery.py) and the platform's HITL/ticket
screens possible without touching the business schema at all.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "db" / "state_graph.db"
_lock = threading.Lock()
_db_path: Path = _DEFAULT_DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS graph_runs (
    run_id TEXT PRIMARY KEY,
    graph_name TEXT NOT NULL,
    agent_name TEXT,
    status TEXT NOT NULL,           -- running | waiting | hitl_paused | failed | completed
    current_node TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS graph_checkpoints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    checkpoint_seq INTEGER NOT NULL,
    completed_node TEXT NOT NULL,   -- the node whose output this checkpoint captures
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (run_id) REFERENCES graph_runs(run_id)
);
CREATE INDEX IF NOT EXISTS idx_checkpoints_run ON graph_checkpoints(run_id, checkpoint_seq);

CREATE TABLE IF NOT EXISTS hitl_tasks (
    task_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    resume_node TEXT NOT NULL,
    reason TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | approved | rejected
    decision_json TEXT,
    resolved_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (run_id) REFERENCES graph_runs(run_id)
);

CREATE TABLE IF NOT EXISTS failure_tickets (
    ticket_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    node TEXT NOT NULL,
    error_message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',    -- open | investigating | resolved
    checkpoint_seq INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    resolution_notes TEXT,
    FOREIGN KEY (run_id) REFERENCES graph_runs(run_id)
);

CREATE TABLE IF NOT EXISTS agent_tool_permissions (
    agent_name TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    allowed INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (agent_name, tool_name)
);

CREATE TABLE IF NOT EXISTS rag_documents (
    doc_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    added_by TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""


def set_db_path(path) -> None:
    """Point the module at a different SQLite file. Used by tests
    (isolated throwaway DB per test run) and by demo_crash_recovery.py
    (a dedicated demo DB), exactly like mcp_server.database.DB_PATH is
    swapped by graph_conftest.py's business_db fixture."""
    global _db_path
    with _lock:
        _db_path = Path(path)
        _db_path.parent.mkdir(parents=True, exist_ok=True)


def get_db_path() -> Path:
    return _db_path


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_db_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # durability + safe concurrent admin/graph writers
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema() -> None:
    _db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
