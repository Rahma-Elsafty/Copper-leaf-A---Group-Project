# State Graphs & Platform — Final Project Addition

This document covers what's new in this drop: the `state_graph/` engine and
its three graphs (already scaffolded by a teammate), and the `platform/`
folder + supporting fixes I added on top so the whole thing is actually
reachable end to end, per the Final Project spec.

**Merge instructions:** this zip assumes it lands inside the existing
`Copper-leaf-A---Group-Project` repo, sitting next to the already-present
`mcp_server/`, `db/`, `rag/`, `agent/`, `planning/` folders from the prior
three labs. It does **not** duplicate those — `mcp_server/server.py` is the
one file here that patches an existing file in place (see "What I fixed"
below); everything else it imports (`tools_read`, `tools_write`, `database`,
`resources`, `prompts`) is assumed to already exist in your checkout
exactly as before.

```
your-repo/
├── state_graph/            <- NEW (this drop)
│   ├── engine.py              (from teammate + retry_from_ticket added)
│   ├── store.py               (from teammate + list_known_agents added)
│   ├── db.py                  (from teammate, unchanged)
│   ├── mcp_bridge.py          (from teammate, unchanged)
│   ├── techniques.py          (from teammate + RAG-fallback fix)
│   ├── demo_crash_recovery.py (from teammate, unchanged)
│   └── graphs/
│       ├── supplier_onboarding.py
│       ├── food_safety_incident.py
│       └── purchase_order_fulfillment.py
├── tests/state_graph/       <- NEW (this drop) — the teammate's test suite
├── platform/                 <- NEW (this drop) — the actual product surface
│   ├── backend.py
│   ├── requirements.txt
│   └── static/ (index.html, app.js, style.css)
├── mcp_server/server.py      <- PATCHED (this drop) — see "What I fixed"
├── mcp_server/tool_defs.py   <- NEW (this drop) — shared tool metadata
├── pytest.ini                <- NEW (this drop)
└── (everything else: unchanged, not included in this drop)
```

## The three state-graph problems (owned by this drop's graphs)

| Graph | Real multi-sitting wait | Real HITL | Real un-retryable failure | Two LLM-call additions |
|---|---|---|---|---|
| `supplier_onboarding` | waits on the supplier signing and returning an agreement (days) | marking a supplier verified changes every future PO's approval exposure | supplier never returns a signed agreement in the window | RAG (compliance grounding) + constrained ReAct (whitelisted `get_supplier` lookup only) |
| `food_safety_incident` | waits on a follow-up re-inspection, on the food-safety officer's schedule | closing an incident is irreversible/liability-relevant, unconditional HITL | a re-inspection result the graph can't parse | RAG (safety-policy grounding) + Tree of Thoughts (ranks candidate corrective actions via `planning.tree_of_thoughts` directly) |
| `purchase_order_fulfillment` | waits on the supplier's actual delivery (hours–days) | order exceeds 80% of remaining budget OR supplier unverified | delivered qty off by >5%, or delivery never arrives | Task decomposition (per order-line dispatch) + constrained ReAct (whitelisted `approve_purchase_order`/`record_inventory_count`) |

None of these three re-skins the Decomposition & Planning Lab's scheduling
problem or the Memory & RAG Lab's retrieval problem — see each graph
module's own docstring for the full "why this needs a state graph, not a
for-loop" argument.

## What I fixed (this drop, on top of what was already there)

1. **RAG documents added via the platform were being silently ignored.**
   `state_graph/store.py` already had `add_rag_document` /
   `remove_rag_document` writing to a real `rag_documents` table, but
   `state_graph/techniques.py::retrieve_grounding`'s fallback path only ever
   read `safety_policies` — an admin's add/remove through the platform had
   no effect on the next query. Fixed: the fallback now also searches
   `rag_documents`, tagging results `"source": "admin_rag_document"` so
   it's visible which table a given grounding hit came from.

2. **MCP tool availability was a hardcoded list with no runtime control.**
   `mcp_server/server.py`'s `on_list_tools`/`on_call_tool` now check
   `state_graph.store.is_tool_allowed(AGENT_NAME, tool_name)` on **every**
   request — the same permission table and the same check
   `state_graph/mcp_bridge.py` already used for in-process graph-node tool
   calls. An admin flipping a tool off in the platform is visible on the
   server's very next request, no redeploy. `AGENT_NAME` comes from the
   `MCP_AGENT_NAME` environment variable (defaults to `"default_agent"`),
   matching a per-agent server config.

3. **The ticket/failure-recovery path had no resume.** `state_graph/
   engine.py` had `advance_waiting_run` (for `Wait`) and
   `resolve_hitl_and_resume` (for `HitlPause`), but nothing to resume a run
   after a `NodeFailure`-generated ticket was resolved — the spec explicitly
   requires resuming "exactly from that checkpoint... not restarted from
   the beginning." Added `StateGraph.retry_from_ticket(run_id, node_name,
   event)`, which the platform's ticket-resolve endpoint calls only after
   `store.update_ticket_status(..., "resolved", ...)` has actually been
   recorded — resolving a ticket and resuming its run stay two explicit
   steps, never one hidden auto-action.

4. **There was no product surface at all.** Nothing in the prior drop let
   an admin or a real user reach any of this outside a test file or a
   script — that's the whole `platform/` folder below.

## The platform

Run it:

```bash
cd your-repo
pip install -r platform/requirements.txt
python platform/backend.py
```

Then open **http://localhost:5000**. The Flask process serves both the
JSON API and the static frontend, so there's exactly one process to run
for a local demo. (Run it as `python platform/backend.py`, not
`python -m platform.backend` — Python's standard library already has a
module named `platform`, and running it as a script avoids that name
colliding with the package import machinery.)

**Admin surface**
- **Agents & tools** — toggle any tool on/off per agent; reaches the live
  MCP server (see fix #2).
- **RAG documents** — add/remove documents used by `retrieve_grounding`
  (see fix #1).
- **HITL queue** — open a pending task, see the run's persisted payload,
  approve or reject with notes; the underlying run resumes immediately
  through `resolve_hitl_and_resume`.
- **Failure tickets** — open a ticket, see the error and the run/node it
  came from, resolve it, optionally retry the run from its last
  checkpoint (`retry_from_ticket`) with corrected data.

**User surface**
- **Chat** — switch between the Memory/RAG agent and the Planning agent
  (calls `agent/client.py` and `agent/planning_agent/main.py` from the
  prior labs, which weren't part of this drop's file set — the endpoint
  imports them defensively and reports a clear message if they aren't
  importable in your checkout; once this lands in the real repo where
  those modules exist, it works with no further changes).
- **State-graph runs** — start a new supplier-onboarding / food-safety /
  purchase-order request with real fields, see its live pipeline position,
  deliver external events (deliveries, signed agreements, re-inspections)
  or simulate a timeout, and inspect its full checkpointed state.

## Crash-and-resume demo (already provided)

```bash
python -m state_graph.demo_crash_recovery
```

Starts a purchase-order run in a real subprocess, SIGKILLs it mid-`Wait`,
then resumes it in a second, independent process from its last checkpoint.
Output shows the checkpoint trace proving no completed node re-executes.

## Running the test suite

```bash
pip install pytest
pytest
```

(`pytest.ini` adds the repo root to `sys.path` so `tests/state_graph/*`
can `from state_graph import store` / `from state_graph.graphs.X import
build_graph` the same way the graph modules themselves do. These tests
also import `mcp_server.database`, `mcp_server.tools_read`, etc., which
must already be present in your checkout from the prior labs.)

## Still to do (not part of this drop)

- Wire the Chat tab's two agent entrypoints once `agent/client.py` and
  `agent/planning_agent/main.py` are confirmed importable in your actual
  checkout (they should already "just work" — see note above).
- Point the platform's timeout sweep at a real scheduler (e.g. an admin
  cron hitting `POST /api/admin/timeouts/sweep`) instead of the manual
  "simulate timeout" button, if you want it running unattended.
- Record the three pieces of demo evidence the spec asks for (HITL
  resolve, ticket resolve+retry, kill-and-resume) — the platform and
  `demo_crash_recovery.py` are both built to make each of those a
  straightforward screen recording.
