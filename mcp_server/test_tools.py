"""
test_tools.py -- standalone sanity check for tool handlers, bypassing the
MCP transport entirely. Calls handler functions directly with fake
arguments dicts so you can verify auth/budget/progress logic in isolation
before wiring up the real server or an agent.

Run: python test_tools.py
"""

import asyncio
import sys
import os

# Adjust this if mcp_server/ isn't a sibling of this file.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "mcp_server"))

from db import build_db_if_missing
from tools_read import handle_list_low_stock_items, handle_get_recipe_allergens
from tools_write import handle_place_purchase_order
from tools_progress import handle_run_inventory_audit


def section(title):
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


class FakeMeta:
    """Simulates request_context.meta -- no progressToken means the client
    didn't ask for progress updates, which run_inventory_audit should
    handle gracefully."""
    progressToken = None


class FakeRequestContext:
    """Minimal stand-in for server.request_context so we can call the
    progress-tracking handler without a real MCP session."""
    meta = FakeMeta()
    session = None  # not used since progress_token is None


def main():
    import os
    DB_FILE = os.path.join(os.path.dirname(__file__), "db", "copperleaf.db")
    if os.path.exists(DB_FILE):
     os.remove(DB_FILE)
    build_db_if_missing()
    
    build_db_if_missing()

    # ---- Read tools (quick smoke test) ----
    section("get_recipe_allergens: Shrimp Risotto (item_id=1)")
    for r in handle_get_recipe_allergens({"item_id": 1}):
        print(r.text)

    section("list_low_stock_items: Downtown (location_id=1)")
    for r in handle_list_low_stock_items({"location_id": 1}):
        print(r.text)

    # ---- place_purchase_order: auth rejection ----
    # staff_id=1 is Maria Alvarez, a line_cook at Downtown -- must be
    # rejected regardless of order size.
    section("place_purchase_order: line_cook attempts an order (expect REJECT: role)")
    for r in handle_place_purchase_order({
        "ingredient_id": 2,
        "supplier_id": 1,
        "qty": 5,
        "unit_cost": 10.0,
        "requested_by": 1,
    }):
        print(r.text)

    # ---- place_purchase_order: budget rejection ----
    # staff_id=2 is James Whitfield, kitchen_manager at Downtown.
    # Downtown budget=5000; PO#1 approved (150) + PO#2 pending (4500) = 4650
    # committed, so only ~350 remains. This order (qty 10 * 50 = 500)
    # should blow that remaining budget.
    section("place_purchase_order: kitchen_manager over remaining budget (expect REJECT: budget)")
    for r in handle_place_purchase_order({
        "ingredient_id": 2,
        "supplier_id": 2,
        "qty": 10,
        "unit_cost": 50.0,
        "requested_by": 2,
    }):
        print(r.text)

    # ---- place_purchase_order: should succeed ----
    # Same kitchen_manager, small order well under the ~350 remaining.
    section("place_purchase_order: kitchen_manager, in-budget order (expect PENDING success)")
    for r in handle_place_purchase_order({
        "ingredient_id": 4,
        "supplier_id": 2,
        "qty": 2,
        "unit_cost": 20.0,
        "requested_by": 2,
    }):
        print(r.text)

    # ---- run_inventory_audit: progress tracking, no progressToken ----
    section("run_inventory_audit: Downtown (location_id=1), no progressToken")
    ctx = FakeRequestContext()
    results = asyncio.run(
        handle_run_inventory_audit({"location_id": 1, "batch_size": 3}, ctx)
    )
    for r in results:
        print(r.text)


if __name__ == "__main__":
    main()