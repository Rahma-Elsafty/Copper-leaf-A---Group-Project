"""
state_graph/mcp_bridge.py — lets a state-graph node call a REAL MCP tool
without opening a second stdio session to mcp_server/server.py.

Why this is not a parallel/fake MCP layer: `TOOL_REGISTRY` below points at
the EXACT SAME functions mcp_server/server.py's `on_call_tool` dispatches
to (mcp_server.tools_write.place_purchase_order, etc.) — this module just
calls them in-process instead of over stdio, because a state-graph node
running as part of an agent process doesn't need the wire protocol to reach
code that already lives in the same Python environment. The permission
check below is the SAME `state_graph.store.is_tool_allowed` check
mcp_server/server.py::on_call_tool performs for stdio calls (see that
file), so an admin disabling a tool for an agent in the platform blocks
that agent's state-graph nodes exactly the same way it blocks its stdio
tool calls.
"""
from __future__ import annotations

from typing import Any, Callable

from state_graph import store


def _load_registry() -> dict[str, Callable[..., Any]]:
    from mcp_server.tools_read import (
        handle_get_recipe_allergens,
        handle_get_supplier,
        handle_list_low_stock_items,
        handle_list_suppliers,
    )
    from mcp_server.tools_write import (
        approve_purchase_order,
        mark_supplier_verified,
        place_purchase_order,
        record_inventory_count,
    )

    return {
        "list_suppliers": lambda args: handle_list_suppliers(args),
        "get_supplier": lambda args: handle_get_supplier(args),
        "list_low_stock_items": lambda args: handle_list_low_stock_items(args),
        "get_recipe_allergens": lambda args: handle_get_recipe_allergens(args),
        "place_purchase_order": lambda args: place_purchase_order(**args),
        "approve_purchase_order": lambda args: approve_purchase_order(**args),
        "mark_supplier_verified": lambda args: mark_supplier_verified(**args),
        "record_inventory_count": lambda args: record_inventory_count(**args),
    }


class ToolPermissionDenied(Exception):
    pass


def make_call_tool(agent_name: str) -> Callable[[str, dict[str, Any]], Any]:
    """Returns a `call_tool(tool_name, arguments)` closure bound to
    `agent_name`, for use as `constrained_react`'s `call_tool` argument.
    Raises ToolPermissionDenied — a NodeFailure-worthy, ticket-generating
    error — if the live agent_tool_permissions table currently disables
    this tool for this agent."""
    registry = None  # lazy: only imported the first time a real call happens

    def call_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
        nonlocal registry
        if not store.is_tool_allowed(agent_name, tool_name):
            raise ToolPermissionDenied(
                f"Agent '{agent_name}' is not currently permitted to call '{tool_name}' "
                "(disabled via the admin platform)."
            )
        if registry is None:
            registry = _load_registry()
        if tool_name not in registry:
            raise ToolPermissionDenied(f"Unknown tool: {tool_name}")
        return registry[tool_name](arguments)

    return call_tool
