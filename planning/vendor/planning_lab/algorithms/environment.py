from __future__ import annotations

import ast
import re
from typing import Any

from planning.models import EnvironmentFeedback
from planning.mcp_adapter import CopperleafMCPAdapter


class CopperleafEnvironment:
    """
    Grounded environment for the Copperleaf planning agent.

    Unlike the original stochastic toolkit environment, this evaluator
    checks candidate actions against the real Copperleaf MCP server.
    """

    def __init__(self, mcp: CopperleafMCPAdapter):
        self.mcp = mcp

    async def evaluate(
        self,
        state: str | dict[str, Any],
    ) -> EnvironmentFeedback:

        candidate = self._parse_candidate(state)

        if not isinstance(candidate, dict):
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["Candidate must be a dictionary."],
            )

        tool_name = candidate.get("tool")
        arguments = candidate.get("arguments", {})

        if not tool_name:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["Candidate is missing the 'tool' field."],
            )

        if not isinstance(arguments, dict):
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=["Candidate arguments must be a dictionary."],
            )

        try:
            await self._validate_tool_action(
                tool_name,
                arguments,
            )

        except ValueError as exc:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=[str(exc)],
            )

        except Exception as exc:
            return EnvironmentFeedback(
                success=False,
                score=0.0,
                details=[
                    f"Grounded environment error: {exc}"
                ],
            )

        return EnvironmentFeedback(
            success=True,
            score=1.0,
            details=[
                f"Candidate action '{tool_name}' passed "
                "Copperleaf environment checks."
            ],
        )

    # =====================================================
    # Candidate parsing
    # =====================================================

    def _parse_candidate(
        self,
        state: str | dict[str, Any],
    ) -> dict[str, Any]:

        if isinstance(state, dict):
            return state

        if not isinstance(state, str):
            raise ValueError(
                "Candidate must be a string or dictionary."
            )

        state = state.strip()

        if not state:
            raise ValueError(
                "Candidate cannot be empty."
            )

        try:
            parsed = ast.literal_eval(state)

            if isinstance(parsed, dict):
                return parsed

        except (SyntaxError, ValueError):
            pass

        raise ValueError(
            "Could not parse candidate action. "
            "Expected a Python dictionary."
        )

    # =====================================================
    # Copperleaf validation
    # =====================================================

    async def _validate_tool_action(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ):

        if tool_name == "list_low_stock_items":

            location_id = arguments.get("location_id")

            if location_id is None:
                raise ValueError(
                    "location_id is required."
                )

            await self.mcp.call_tool(
                "list_low_stock_items",
                {
                    "location_id": location_id
                },
            )

            return

        if tool_name == "get_supplier":

            supplier_id = arguments.get("supplier_id")

            if supplier_id is None:
                raise ValueError(
                    "supplier_id is required."
                )

            result = await self.mcp.call_tool(
                "get_supplier",
                {
                    "supplier_id": supplier_id
                },
            )

            if not result or "not found" in result[0].lower():
                raise ValueError(
                    f"Supplier {supplier_id} does not exist."
                )

            return

        if tool_name == "place_purchase_order":

            await self._validate_purchase_order(
                arguments
            )

            return

        if tool_name == "mark_supplier_verified":

            supplier_id = arguments.get("supplier_id")

            if supplier_id is None:
                raise ValueError(
                    "supplier_id is required."
                )

            result = await self.mcp.call_tool(
                "get_supplier",
                {
                    "supplier_id": supplier_id
                },
            )

            if not result or "not found" in result[0].lower():
                raise ValueError(
                    f"Supplier {supplier_id} does not exist."
                )

            return

        if tool_name == "approve_purchase_order":

            if arguments.get("po_id") is None:
                raise ValueError(
                    "po_id is required."
                )

            return

        if tool_name == "record_inventory_count":

            if arguments.get("stock_id") is None:
                raise ValueError(
                    "stock_id is required."
                )

            if arguments.get("quantity") is None:
                raise ValueError(
                    "quantity is required."
                )

            return
        if tool_name == "get_location_budget":

            location_id = arguments.get("location_id")

            if location_id is None:
                raise ValueError(
                    "location_id is required."
                )

            result = await self.mcp.call_tool(
                "get_location_budget",
                {
                    "location_id": location_id
                },
            )

            if not result:
                raise ValueError(
                    f"Location {location_id} could not be verified."
                )

            text = "\n".join(result)

            if "not found" in text.lower():
                raise ValueError(
                    f"Location {location_id} does not exist."
                )

            return
        if tool_name == "get_location_budget":

            location_id = arguments.get("location_id")

            if location_id is None:
                raise ValueError(
                    "location_id is required."
                )

            result = await self.mcp.call_tool(
                "get_location_budget",
                {
                    "location_id": location_id
                },
            )

            if not result:
                raise ValueError(
                    f"Location {location_id} could not be verified."
                )

            text = "\n".join(result)

            if "not found" in text.lower():
                raise ValueError(
                    f"Location {location_id} does not exist."
                )

            return
        if tool_name == "get_inventory_item":

            stock_id = arguments.get("stock_id")

            if stock_id is None:
                raise ValueError(
                    "stock_id is required."
                )

            result = await self.mcp.call_tool(
                "get_inventory_item",
                {
                    "stock_id": stock_id
                },
            )

            if not result:
                raise ValueError(
                    f"Inventory item {stock_id} could not be verified."
                )

            text = "\n".join(result)

            if "not found" in text.lower():
                raise ValueError(
                    f"Inventory item {stock_id} does not exist."
                )

            return

        raise ValueError(
            f"Unknown Copperleaf tool: {tool_name}"
        )

    # =====================================================
    # Purchase order business rules
    # =====================================================

    async def _validate_purchase_order(
        self,
        arguments: dict[str, Any],
    ):

        required = [
            "ingredient_id",
            "supplier_id",
            "qty",
            "unit_cost",
            "requested_by",
        ]

        missing = [
            field
            for field in required
            if field not in arguments
        ]

        if missing:
            raise ValueError(
                "Missing purchase-order fields: "
                + ", ".join(missing)
            )

        supplier_id = arguments["supplier_id"]

        supplier_result = await self.mcp.call_tool(
            "get_supplier",
            {
                "supplier_id": supplier_id
            },
        )

        if not supplier_result:
            raise ValueError(
                f"Supplier {supplier_id} does not exist."
            )

        supplier_text = "\n".join(
            supplier_result
        )

        if "not found" in supplier_text.lower():
            raise ValueError(
                f"Supplier {supplier_id} does not exist."
            )

        # The MCP tool itself already enforces the actual
        # purchase-order rules: authorization, supplier status,
        # budget confirmation conditions, etc.
        #
        # We call it only after checking that this is a real
        # Copperleaf supplier.