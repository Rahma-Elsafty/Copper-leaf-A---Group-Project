-- Copperleaf MCP Server Project
-- Seed data: SQLite
-- Owner: Person 1
--
-- Deliberately includes the edge cases the fixed test inputs (see README /
-- team plan section 5) depend on:
--   * a location whose remaining budget is thin enough to trigger the
--     80%-of-budget elicitation path on place_purchase_order
--   * an ingredient exactly AT its reorder_threshold (list_low_stock_items
--     boundary case)
--   * an unverified supplier (elicitation trigger + defensive-tool test)
--   * a menu item with two overlapping allergens (allergen resource/tool test)
--   * one staff member of each role (line_cook / kitchen_manager /
--     food_safety_officer) so role-based authorization has real cases
--   * food_safety_incidents rows to drive notifications + sampling tests
--     (INC-1001 already closed as a control, INC-1002 open and used in the
--     fixed test inputs for sampling + prompts)

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- locations
-- ---------------------------------------------------------------------------
INSERT INTO locations (location_id, name, region, monthly_budget) VALUES
    (1, 'Downtown Kitchen',      'Metro',    5000.00),
    (2, 'Riverside Kitchen',     'Metro',    4000.00),
    (3, 'Shared Commercial Kitchen', 'Central', 12000.00);

-- ---------------------------------------------------------------------------
-- staff  (one of each role per relevant location)
-- ---------------------------------------------------------------------------
INSERT INTO staff (staff_id, name, role, location_id) VALUES
    (1, 'Maria Alvarez',  'line_cook',           1),
    (2, 'James Whitfield','kitchen_manager',     1),
    (3, 'Dana Okafor',    'food_safety_officer',  1),
    (4, 'Tomas Reyes',    'line_cook',           2),
    (5, 'Priya Nair',     'kitchen_manager',     2),
    (6, 'Ellis Boone',    'food_safety_officer',  3);

-- ---------------------------------------------------------------------------
-- ingredients (allergen_tags comma-separated; '' = none known)
-- ---------------------------------------------------------------------------
INSERT INTO ingredients (ingredient_id, name, allergen_tags) VALUES
    (1, 'Shrimp',            'shellfish'),
    (2, 'Arborio Rice',      ''),
    (3, 'Heavy Cream',       'dairy'),
    (4, 'Parmesan Cheese',   'dairy'),
    (5, 'Peanut Oil',        'nuts'),
    (6, 'All-Purpose Flour', 'gluten'),
    (7, 'Chicken Breast',    ''),
    (8, 'Butter',            'dairy');

-- ---------------------------------------------------------------------------
-- menu_items
-- ---------------------------------------------------------------------------
INSERT INTO menu_items (item_id, name, location_id, price) VALUES
    (1, 'Shrimp Risotto',     1, 24.00),  -- overlapping allergens: shellfish + dairy
    (2, 'Grilled Chicken',    1, 18.00),
    (3, 'Peanut Noodle Bowl', 2, 16.00),
    (4, 'Garlic Bread',       2, 6.00);

-- ---------------------------------------------------------------------------
-- recipe_ingredients (junction) -- Shrimp Risotto deliberately pulls two
-- allergen tags (shellfish via shrimp, dairy via cream + parmesan)
-- ---------------------------------------------------------------------------
INSERT INTO recipe_ingredients (item_id, ingredient_id, quantity) VALUES
    (1, 1, 0.20),  -- Shrimp Risotto: shrimp
    (1, 2, 0.15),  -- Shrimp Risotto: arborio rice
    (1, 3, 0.10),  -- Shrimp Risotto: heavy cream
    (1, 4, 0.05),  -- Shrimp Risotto: parmesan
    (2, 7, 0.25),  -- Grilled Chicken: chicken breast
    (2, 8, 0.02),  -- Grilled Chicken: butter
    (3, 5, 0.05),  -- Peanut Noodle Bowl: peanut oil
    (3, 6, 0.10),  -- Peanut Noodle Bowl: flour (noodles)
    (4, 6, 0.20),  -- Garlic Bread: flour
    (4, 8, 0.05);  -- Garlic Bread: butter

-- ---------------------------------------------------------------------------
-- inventory_stock
--   Note: ingredient 1 (Shrimp) at Downtown is exactly AT reorder_threshold
--   -- deliberate boundary case for list_low_stock_items.
-- ---------------------------------------------------------------------------
INSERT INTO inventory_stock (stock_id, ingredient_id, location_id, qty_on_hand, reorder_threshold) VALUES
    (1, 1, 1, 10.0, 10.0),   -- Shrimp @ Downtown: AT threshold (edge case)
    (2, 2, 1, 40.0, 15.0),   -- Rice @ Downtown: healthy stock
    (3, 3, 1, 8.0,  10.0),   -- Cream @ Downtown: below threshold (low stock)
    (4, 4, 1, 12.0, 5.0),    -- Parmesan @ Downtown: healthy stock
    (5, 5, 2, 3.0,  8.0),    -- Peanut oil @ Riverside: below threshold
    (6, 6, 2, 25.0, 10.0),   -- Flour @ Riverside: healthy stock
    (7, 7, 1, 20.0, 10.0),   -- Chicken @ Downtown: healthy stock
    (8, 8, 2, 6.0,  6.0);    -- Butter @ Riverside: AT threshold (edge case)

-- ---------------------------------------------------------------------------
-- suppliers (one unverified -- elicitation + defensive-tool trigger)
-- ---------------------------------------------------------------------------
INSERT INTO suppliers (supplier_id, name, verified, contact) VALUES
    (1, 'Gulf Coast Seafood Co.',   1, 'orders@gulfcoastseafood.example'),
    (2, 'Rocky Mountain Dairy',     1, 'sales@rmdairy.example'),
    (3, 'Bargain Bulk Foods LLC',   0, 'contact@bargainbulk.example'); -- unverified

-- ---------------------------------------------------------------------------
-- purchase_orders
--   PO 1: normal, small, approved historically (control case)
--   PO 2: pending, deliberately sized close to 90% of Downtown's remaining
--         budget -- used by the fixed elicitation test input
-- ---------------------------------------------------------------------------
INSERT INTO purchase_orders (po_id, ingredient_id, supplier_id, qty, cost, status, requested_by, created_at) VALUES
    (1, 2, 2, 50.0,  150.00,  'approved', 2, datetime('now', '-5 days')),
    (2, 1, 1, 200.0, 4500.00, 'pending',  2, datetime('now'));
    -- Downtown monthly_budget = 5000.00; this PO alone is 90% of the full
    -- budget (and effectively all remaining budget after PO #1), which is
    -- exactly the "90% of remaining budget" fixed test input for elicitation.

-- ---------------------------------------------------------------------------
-- food_safety_incidents
--   INC-1001 (id 1): older, already closed -- control/non-triggering case
--   INC-1002 (id 2): open temperature breach at Downtown -- drives the
--   notifications, sampling, and prompts fixed test inputs
-- ---------------------------------------------------------------------------
INSERT INTO food_safety_incidents (incident_id, location_id, type, opened_by, status, summary, created_at) VALUES
    (1, 2, 'cross_contamination', 4, 'closed', 'Cutting board mix-up resolved; board replaced and staff retrained.', datetime('now', '-10 days')),
    (2, 1, 'temperature_breach',  1, 'open',   NULL, datetime('now'));
    -- INC-1002's summary is intentionally NULL: Person 2's sampling/createMessage
    -- call is what populates it from raw temperature-log readings.

-- ---------------------------------------------------------------------------
-- safety_policies (standalone reference data, exposed via resources/read)
-- ---------------------------------------------------------------------------
INSERT INTO safety_policies (policy_id, title, doc_text) VALUES
    (1, 'Cold Holding Temperature Procedure',
        'All potentially hazardous food must be held at 41F (5C) or below. ' ||
        'Walk-in and reach-in units must be checked and logged at the start ' ||
        'of each shift and every 4 hours thereafter. If a unit reads above ' ||
        '41F, food safety officer must be notified immediately, the unit ' ||
        'must be tagged out of service, and all potentially hazardous ' ||
        'contents held in that unit for longer than 2 hours above 41F must ' ||
        'be discarded and logged as a temperature-breach incident.'),
    (2, 'Cross-Contamination Prevention Procedure',
        'Raw proteins and ready-to-eat foods must use separate, color-coded ' ||
        'cutting boards and utensils at all times. Any suspected cross-contact ' ||
        'event must be logged as a food safety incident within one hour of ' ||
        'discovery, including the items involved and the corrective action taken.'),
    (3, 'Purchase Order Approval Policy',
        'Purchase orders may only be placed by kitchen managers. Any order ' ||
        'that would use more than 80 percent of a location''s remaining ' ||
        'monthly budget, or that is placed with a supplier not marked as ' ||
        'verified, requires explicit confirmation from a human before the ' ||
        'order is finalized.');