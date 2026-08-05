-- Copperleaf MCP Server Project
-- Schema: SQLite
-- Owner: Person 1
--
-- Notes:
--   * PRAGMA foreign_keys must be turned ON by the app/connection (SQLite defaults it OFF).
--   * status/role/allergen_tags fields use CHECK constraints to keep them constrained
--     even though the MCP tool schemas will ALSO validate these independently.

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- locations
-- ---------------------------------------------------------------------------
CREATE TABLE locations (
    location_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name             TEXT NOT NULL,
    region           TEXT NOT NULL,
    monthly_budget   REAL NOT NULL CHECK (monthly_budget >= 0)
);

-- ---------------------------------------------------------------------------
-- staff
-- ---------------------------------------------------------------------------
CREATE TABLE staff (
    staff_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('line_cook', 'kitchen_manager', 'food_safety_officer')),
    location_id  INTEGER NOT NULL REFERENCES locations(location_id)
);

-- ---------------------------------------------------------------------------
-- menu_items
-- ---------------------------------------------------------------------------
CREATE TABLE menu_items (
    item_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    location_id  INTEGER NOT NULL REFERENCES locations(location_id),
    price        REAL NOT NULL CHECK (price >= 0)
);

-- ---------------------------------------------------------------------------
-- ingredients
-- ---------------------------------------------------------------------------
-- allergen_tags stored as a comma-separated list (e.g. "shellfish,dairy").
-- Kept simple for SQLite; a stricter design would normalize this into its own
-- ingredient_allergens table, but this is enough for the lab's needs.
CREATE TABLE ingredients (
    ingredient_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    allergen_tags  TEXT NOT NULL DEFAULT ''  -- '' means no known allergens
);

-- ---------------------------------------------------------------------------
-- recipe_ingredients (junction: menu_items <-> ingredients)
-- ---------------------------------------------------------------------------
CREATE TABLE recipe_ingredients (
    item_id        INTEGER NOT NULL REFERENCES menu_items(item_id),
    ingredient_id  INTEGER NOT NULL REFERENCES ingredients(ingredient_id),
    quantity       REAL NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (item_id, ingredient_id)
);

-- ---------------------------------------------------------------------------
-- inventory_stock
-- ---------------------------------------------------------------------------
CREATE TABLE inventory_stock (
    stock_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id     INTEGER NOT NULL REFERENCES ingredients(ingredient_id),
    location_id       INTEGER NOT NULL REFERENCES locations(location_id),
    qty_on_hand       REAL NOT NULL CHECK (qty_on_hand >= 0),
    reorder_threshold REAL NOT NULL CHECK (reorder_threshold >= 0),
    UNIQUE (ingredient_id, location_id)
);

-- ---------------------------------------------------------------------------
-- suppliers
-- ---------------------------------------------------------------------------
CREATE TABLE suppliers (
    supplier_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    verified     INTEGER NOT NULL DEFAULT 0 CHECK (verified IN (0, 1)),
    contact      TEXT
);

-- ---------------------------------------------------------------------------
-- purchase_orders
-- ---------------------------------------------------------------------------
CREATE TABLE purchase_orders (
    po_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ingredient_id INTEGER NOT NULL REFERENCES ingredients(ingredient_id),
    supplier_id   INTEGER NOT NULL REFERENCES suppliers(supplier_id),
    qty           REAL NOT NULL CHECK (qty > 0),
    cost          REAL NOT NULL CHECK (cost >= 0),
    status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    requested_by  INTEGER NOT NULL REFERENCES staff(staff_id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- food_safety_incidents
-- ---------------------------------------------------------------------------
CREATE TABLE food_safety_incidents (
    incident_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    location_id  INTEGER NOT NULL REFERENCES locations(location_id),
    type         TEXT NOT NULL CHECK (type IN ('temperature_breach', 'cross_contamination', 'other')),
    opened_by    INTEGER NOT NULL REFERENCES staff(staff_id),
    status       TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'corrective_action_logged', 'closed')),
    summary      TEXT,  -- populated via sampling/createMessage by Person 2's code
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- safety_policies (standalone reference data - exposed via resources/read,
-- never wrapped in a tool, no FK relationships to anything else)
-- ---------------------------------------------------------------------------
CREATE TABLE safety_policies (
    policy_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT NOT NULL UNIQUE,
    doc_text   TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- Helpful indexes (not strictly required, but keep the read tools fast)
-- ---------------------------------------------------------------------------
CREATE INDEX idx_staff_location ON staff(location_id);
CREATE INDEX idx_inventory_location ON inventory_stock(location_id);
CREATE INDEX idx_po_status ON purchase_orders(status);
CREATE INDEX idx_incidents_location_status ON food_safety_incidents(location_id, status);