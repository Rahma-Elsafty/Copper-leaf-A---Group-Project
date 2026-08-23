"""
planning/environment.py — grounded EnvironmentFeedback source for LATS.
Owned by Person 3. Replaces the toolkit's randomized `Environment`
(algorithms/environment.py, a `betavariate` coin flip with no connection to
reality) entirely.

Grounding: a candidate purchase order is graded by ACTUALLY calling the
real `place_purchase_order` MCP tool against the real database — not a
random number, not the model's opinion of itself.

  - success = the server accepted the order with requires_confirmation=False
              (no budget or supplier-verification problem).
  - score   = 1.0 on a clean accept, 0.4 if it needed human confirmation
              (the order is structurally valid but risky), 0.0 on an
              outright rejection/exception.
  - details = the EXACT `reasons` the server returned (e.g. "Order exceeds
              80% of remaining budget."), so LATS's branch-level reflection
              is grounded in a real fact pulled from the server, not a
              guess.

This is the concrete difference an ungrounded LATS would miss: a candidate
that overspends a location's real remaining budget scores badly here every
time, because the server itself says so. A self-critique with no database
access has no way to know the location's actual remaining budget and would
happily approve an over-budget order.
"""
from __future__ import annotations

import ast

from .dag import EnvironmentFeedback
from .decomposition import MCPClient
from .lats import PurchaseOrderCandidate


class RestockEnvironment:
    def __init__(self, mcp_client: MCPClient, requested_by: int):
        self.mcp_client = mcp_client
        self.requested_by = requested_by

    async def evaluate(self, candidate: PurchaseOrderCandidate) -> EnvironmentFeedback:
        try:
            raw = await self.mcp_client.call_mcp_tool(
                "place_purchase_order",
                {
                    "ingredient_id": candidate.ingredient_id,
                    "supplier_id": candidate.supplier_id,
                    "qty": candidate.qty,
                    "unit_cost": candidate.unit_cost,
                    "requested_by": self.requested_by,
                },
            )
        except Exception as exc:  # noqa: BLE001 — any transport/auth/validation error is a real grounded failure
            return EnvironmentFeedback(success=False, score=0.0, details=[f"MCP call failed: {exc}"])

        try:
            result = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            return EnvironmentFeedback(success=False, score=0.0, details=[f"Unparseable server response: {raw}"])

        if not isinstance(result, dict) or "status" not in result:
            return EnvironmentFeedback(success=False, score=0.0, details=[f"Unexpected server response: {raw}"])

        requires_confirmation = bool(result.get("requires_confirmation", False))
        reasons = [str(reason) for reason in result.get("reasons", [])]

        if not requires_confirmation:
            return EnvironmentFeedback(success=True, score=1.0, details=[])

        # A structurally valid order that still needs a human — partial
        # credit, and the exact reason becomes the branch reflection's
        # grounding fact (see planning/lats.py's failure-reflection call).
        return EnvironmentFeedback(success=False, score=0.4, details=reasons or ["Requires human confirmation."])
