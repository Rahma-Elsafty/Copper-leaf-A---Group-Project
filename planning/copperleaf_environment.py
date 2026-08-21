from __future__ import annotations

import ast
from typing import Any

from .mcp_adapter import CopperleafMCPAdapter
from planning.models import EnvironmentFeedback


class CopperleafEnvironment:
    """
    Grounded environment for the Copperleaf Kitchen planning agent.

    The evaluator uses real MCP tools backed by the Copperleaf SQLite
    database instead of randomized evaluation.
    """

    def __init__(self, mcp: CopperleafMCPAdapter):
        self.mcp = mcp

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    async def _tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> str:

        results = await self.mcp.call_tool(
            name,
            arguments,
        )

        return "\n".join(results)

    @staticmethod
    def _parse_dict(text: str) -> dict[str, Any] | None:
        """
        Parse the textual dictionary returned by Copperleaf tools.
        """

        try:
            value = ast.literal_eval(text)

            if isinstance(value, dict):
                return value

        except (ValueError, SyntaxError):
            pass

        return None

    # ---------------------------------------------------------
    # Purchase Order Evaluation
    # ---------------------------------------------------------

    async def evaluate_purchase_order(
        self,
        *,
        candidate: str,
        ingredient_id: int,
        supplier_id: int,
        qty: float,
        unit_cost: float,
        requested_by: int,
    ) -> EnvironmentFeedback:

        details: list[str] = []

        checks = 0
        passed = 0

        # =====================================================
        # 1. STAFF / AUTHORIZATION
        # =====================================================

        staff_text = await self._tool(
            "get_staff",
            {
                "staff_id": requested_by,
            },
        )

        staff = self._parse_dict(staff_text)

        checks += 1

        if staff and staff.get("role") == "kitchen_manager":
            passed += 1
        else:
            details.append(
                "The requester is not a kitchen manager."
            )

        # =====================================================
        # 2. SUPPLIER VERIFICATION
        # =====================================================

        supplier_text = await self._tool(
            "get_supplier",
            {
                "supplier_id": supplier_id,
            },
        )

        supplier = self._parse_dict(supplier_text)

        checks += 1

        if supplier and supplier.get("verified") in (1, True):
            passed += 1
        else:
            details.append(
                "The selected supplier is not verified."
            )

        # =====================================================
        # 3. LOCATION / BUDGET
        # =====================================================

        location_id = (
            staff.get("location_id")
            if staff
            else None
        )

        budget = None

        if location_id is not None:

            budget_text = await self._tool(
                "get_location_budget",
                {
                    "location_id": location_id,
                },
            )

            budget = self._parse_dict(
                budget_text
            )

        checks += 1

        order_cost = qty * unit_cost

        if budget:

            remaining = budget["remaining_budget"]

            threshold = remaining * 0.80

            if order_cost <= threshold:
                passed += 1
            else:
                details.append(
                    "The order exceeds 80% of the remaining budget."
                )

        else:

            details.append(
                "Could not verify the location budget."
            )

        # =====================================================
        # 4. HUMAN CONFIRMATION
        # =====================================================

        checks += 1

        candidate_lower = candidate.lower()

        confirmation_terms = (
            "confirmation",
            "confirm",
            "human approval",
            "manager approval",
        )

        requires_confirmation = False

        if supplier and supplier.get("verified") not in (1, True):
            requires_confirmation = True

        if budget:
            if order_cost > budget["remaining_budget"] * 0.80:
                requires_confirmation = True

        if requires_confirmation:

            if any(
                term in candidate_lower
                for term in confirmation_terms
            ):
                passed += 1
            else:
                details.append(
                    "The plan requires human confirmation "
                    "but does not explicitly include it."
                )

        else:

            passed += 1

        # =====================================================
        # FINAL SCORE
        # =====================================================

        score = (
            passed / checks
            if checks
            else 0.0
        )

        success = len(details) == 0

        return EnvironmentFeedback(
            success=success,
            score=round(score, 4),
            details=details,
        )

    # ---------------------------------------------------------
    # Generic evaluator
    # ---------------------------------------------------------

    async def evaluate(
        self,
        task: str,
        candidate: str,
    ) -> EnvironmentFeedback:

        task_lower = task.lower()

        if "purchase order" in task_lower:

            return await self.evaluate_purchase_order(
                candidate=candidate,

                # Copperleaf seeded test case:
                ingredient_id=1,
                supplier_id=1,
                qty=200,
                unit_cost=22.5,
                requested_by=2,
            )

        return EnvironmentFeedback(
            success=False,
            score=0.0,
            details=[
                "No grounded evaluator is registered "
                "for this Copperleaf task."
            ],
        )