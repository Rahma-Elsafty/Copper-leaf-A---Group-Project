"""Shared helper for graph integration tests. Not named conftest.py on
purpose (it's imported explicitly, not auto-collected) since it needs to
run AFTER the package-level conftest's isolated_db fixture is active for
some tests and independently in others."""
import sqlite3
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture
def business_db(tmp_path, monkeypatch):
    """A throwaway copy of the real business database (schema.sql + a
    small seed), so graph nodes that call mcp_server.database /
    mcp_server.tools_write against 'the real DB' hit a real, disposable
    SQLite file instead of the actual db/copperleaf.db."""
    db_path = tmp_path / "business_test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript((REPO_ROOT / "db" / "schema.sql").read_text(encoding="utf-8"))

    conn.executescript(
        """
        INSERT INTO locations (location_id, name, region, monthly_budget)
            VALUES (1, 'Downtown', 'North', 5000.0);
        INSERT INTO staff (staff_id, name, role, location_id)
            VALUES (2, 'Alex Kitchen Manager', 'kitchen_manager', 1);
        INSERT INTO staff (staff_id, name, role, location_id)
            VALUES (3, 'Sam Food Safety Officer', 'food_safety_officer', 1);
        INSERT INTO suppliers (supplier_id, name, verified, contact)
            VALUES (1, 'Fresh Farms Co', 1, 'fresh@example.com');
        INSERT INTO suppliers (supplier_id, name, verified, contact)
            VALUES (2, 'New Produce Ltd', 0, 'new@example.com');
        INSERT INTO ingredients (ingredient_id, name, allergen_tags)
            VALUES (1, 'Tomatoes', '');
        INSERT INTO inventory_stock (stock_id, ingredient_id, location_id, qty_on_hand, reorder_threshold)
            VALUES (1, 1, 1, 5.0, 10.0);
        INSERT INTO purchase_orders (po_id, ingredient_id, supplier_id, qty, cost, status, requested_by)
            VALUES (100, 1, 1, 50, 150.0, 'pending', 2);
        INSERT INTO purchase_orders (po_id, ingredient_id, supplier_id, qty, cost, status, requested_by)
            VALUES (101, 1, 2, 500, 4200.0, 'pending', 2);
        INSERT INTO food_safety_incidents (incident_id, location_id, type, opened_by, status)
            VALUES (1, 1, 'temperature_breach', 3, 'open');
        INSERT INTO safety_policies (policy_id, title, doc_text)
            VALUES (1, 'Temperature Breach Response',
                    'If a refrigeration unit breaches safe temperature, discard any food held above 40F for more than 2 hours, log the incident, and re-inspect within 24 hours.');
        """
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr("mcp_server.database.DB_PATH", db_path)
    return db_path
