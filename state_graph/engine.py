"""
state_graph/engine.py — the core state-graph execution engine.

A graph here is a dict of {node_name: callable(state) -> NodeResult},
executed by StateGraph, with EVERY meaningful transition (each node
completing) durably checkpointed via state_graph.store BEFORE the engine
even considers moving to the next node. That's what makes
demo_crash_recovery.py's "kill the process mid-run, restart, resume from
the last checkpoint" possible: the checkpoint write happens synchronously,
inside the same call that produced it — not batched, not buffered, not an
execution log written after the fact.

Unlike planning/dag.py's Plan (acyclic, finite, runs start-to-end in one
sitting), a StateGraph can revisit a node it already visited (see
food_safety_incident.investigate, which is a genuine cycle), and can sit
indefinitely in a Wait or hitl_paused state until something OUTSIDE the
model — an admin decision, a webhook, a timeout sweep — resumes it.

Node return contract
---------------------
A node function takes the current `state: dict` and returns exactly one
of:

  Goto(next_node, state_update)
      Continue the graph loop immediately at `next_node`, in the same
      process, same call. Used for ordinary internal transitions.

  Wait(resume_node, reason, state_update)
      Park the run. Some EXTERNAL event that is NOT the model's decision
      (a webhook, a delivery confirmation, a timeout sweep) must call
      `advance_waiting_run()` to continue. Run status becomes 'waiting'.

  HitlPause(resume_node, reason, payload)
      Park the run and open a real task for a human admin. The graph
      resumes ONLY when the platform calls `resolve_hitl_and_resume()`
      after an admin actually acts. Run status becomes 'hitl_paused'.

  Done(state_update)
      The run finished successfully. Run status becomes 'completed'.

...or a node may raise NodeFailure(message) — an UNPLANNED failure (a bad
tool call, a malformed external event, a validation error) that the
engine turns into a real, persisted failure ticket instead of crashing
the process or silently retrying. This is a DIFFERENT code path from
HitlPause: HITL is an expected pause for a decision the agent isn't
allowed to make alone; NodeFailure is the graph hitting something it
genuinely cannot act on.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Union

from state_graph import store

# Guards against a genuine bug (an unbounded Goto cycle) hanging a request
# forever. A legitimate cycle — e.g. food safety's investigate loop —
# pauses on HITL/Wait long before ever approaching this; MAX_INVESTIGATION_CYCLES
# in that graph is a much tighter, domain-specific bound than this one.
MAX_STEPS_PER_INVOCATION = 50


class NodeFailure(Exception):
    """Raise from inside a node to signal an unplanned failure. Caught
    only here, in the engine — nodes never touch state_graph.store's
    ticket functions directly, which keeps 'what counts as a real
    failure' in exactly one place."""


@dataclass
class Goto:
    next_node: str
    state_update: dict = field(default_factory=dict)


@dataclass
class Wait:
    resume_node: str
    reason: str
    state_update: dict = field(default_factory=dict)


@dataclass
class HitlPause:
    resume_node: str
    reason: str
    payload: dict = field(default_factory=dict)


@dataclass
class Done:
    state_update: dict = field(default_factory=dict)


NodeResult = Union[Goto, Wait, HitlPause, Done]
NodeFn = Callable[[dict], NodeResult]


class StateGraph:
    """A named, mutable collection of nodes with one designated start
    node. Built fresh (via each graph module's `build_graph()`) on every
    process/request — nodes are pure functions registered by name, so a
    brand-new StateGraph instance can resume a run that a completely
    different process started, which is exactly what
    demo_crash_recovery.py's second worker process does."""

    def __init__(self, name: str, start_node: str, agent_name: str = None):
        self.name = name
        self.start_node = start_node
        self.agent_name = agent_name or name
        self._nodes: dict[str, NodeFn] = {}

    def add_node(self, name: str, fn: NodeFn) -> None:
        self._nodes[name] = fn

    # -- internal execution loop ---------------------------------------

    def _run_node(self, node_name: str, run_id: str, state: dict) -> None:
        current = node_name
        steps = 0
        while True:
            steps += 1
            if steps > MAX_STEPS_PER_INVOCATION:
                raise RuntimeError(
                    f"Run {run_id} exceeded {MAX_STEPS_PER_INVOCATION} node "
                    "transitions without pausing — likely an unbounded Goto "
                    "cycle bug, not a legitimate graph cycle."
                )

            fn = self._nodes.get(current)
            if fn is None:
                raise RuntimeError(f"Unknown node '{current}' in graph '{self.name}'")

            try:
                result = fn(state)
            except NodeFailure as exc:
                # Checkpoint state AT THE MOMENT OF FAILURE (not the last
                # successful node's state — this node's attempt is what
                # failed), then open a ticket. Distinct table, distinct
                # workflow from HITL.
                seq = store.write_checkpoint(run_id, current, state)
                store.create_failure_ticket(run_id, current, str(exc), seq)
                store.update_run_status(run_id, "failed", current)
                return

            if isinstance(result, Goto):
                state = {**state, **result.state_update}
                store.write_checkpoint(run_id, current, state)
                current = result.next_node
                continue

            if isinstance(result, Wait):
                state = {**state, **result.state_update}
                store.write_checkpoint(run_id, current, state)
                store.update_run_status(run_id, "waiting", result.resume_node)
                return

            if isinstance(result, HitlPause):
                store.write_checkpoint(run_id, current, state)
                store.create_hitl_task(run_id, result.resume_node, result.reason, result.payload)
                store.update_run_status(run_id, "hitl_paused", result.resume_node)
                return

            if isinstance(result, Done):
                state = {**state, **result.state_update}
                store.write_checkpoint(run_id, current, state)
                store.update_run_status(run_id, "completed", current)
                return

            raise TypeError(f"Node '{current}' returned an unrecognized result: {result!r}")

    # -- public API -------------------------------------------------------

    def start(self, initial_state: dict) -> str:
        run_id = store.new_id("run")
        store.create_run(run_id, self.name, self.agent_name, self.start_node)
        self._run_node(self.start_node, run_id, dict(initial_state))
        return run_id

    def resolve_hitl_and_resume(self, run_id: str, resume_node: str, decision: dict) -> None:
        """Called ONLY after a real admin decision has been persisted via
        store.resolve_hitl_task (see the platform's HITL-resolve endpoint,
        or graph_conftest-style tests). Loads the run's LAST CHECKPOINT —
        not a fresh initial_state — so the run resumes exactly where it
        left off, merges the admin's decision into
        state['hitl_decisions'][resume_node], and continues the loop."""
        cp = store.latest_checkpoint(run_id)
        state = dict(cp.state)
        decisions = dict(state.get("hitl_decisions", {}))
        decisions[resume_node] = decision
        state["hitl_decisions"] = decisions
        store.update_run_status(run_id, "running", resume_node)
        self._run_node(resume_node, run_id, state)

    def advance_waiting_run(self, run_id: str, resume_node: str, event: dict) -> None:
        """Called from an external event source: the platform's delivery/
        webhook endpoints, an admin's timeout sweep, or (in
        demo_crash_recovery.py) a second, independent process delivering
        the event after the first process was killed. `event` fields are
        merged directly into state, since a Wait node reads its event
        fields straight off state rather than choosing between named
        decisions the way a HITL apply_*_decision node does."""
        cp = store.latest_checkpoint(run_id)
        state = {**cp.state, **event}
        store.update_run_status(run_id, "running", resume_node)
        self._run_node(resume_node, run_id, state)
