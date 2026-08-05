from mcp.types import TextContent

from mcp_server.database import execute_query
from mcp_server.validation import (
    validate_location_id,
    validate_recipe_item_id,
    validate_supplier_id
)


# --------------------------------------------------
# List Suppliers
# --------------------------------------------------
def handle_list_suppliers(arguments: dict):
    """
    Return all suppliers.
    """

    suppliers = execute_query("""
        SELECT
            supplier_id,
            name,
            verified,
            contact
        FROM suppliers
        ORDER BY name
    """)

    return [
        TextContent(
            type="text",
            text=str(suppliers),
        )
    ]


# --------------------------------------------------
# Get Supplier
# --------------------------------------------------
def handle_get_supplier(arguments: dict):
    """
    Return one supplier by ID.
    """

    supplier_id = arguments["supplier_id"]
    validate_supplier_id(supplier_id)

    rows = execute_query("""
        SELECT
            supplier_id,
            name,
            verified,
            contact
        FROM suppliers
        WHERE supplier_id = ?
    """, (supplier_id,))

    if not rows:
        return [
            TextContent(
                type="text",
                text="Supplier not found.",
            )
        ]

    return [
        TextContent(
            type="text",
            text=str(rows[0]),
        )
    ]


# --------------------------------------------------
# List Low Stock Items
# --------------------------------------------------
def handle_list_low_stock_items(arguments: dict):
    """
    Return ingredients whose quantity is
    less than or equal to the reorder threshold.
    """
    location_id = arguments["location_id"]
    validate_location_id(location_id)
    


    rows = execute_query("""
        SELECT
            ingredients.name,
            inventory_stock.qty_on_hand,
            inventory_stock.reorder_threshold
        FROM inventory_stock
        JOIN ingredients
            ON inventory_stock.ingredient_id =
               ingredients.ingredient_id
        WHERE inventory_stock.location_id = ?
          AND inventory_stock.qty_on_hand <=
              inventory_stock.reorder_threshold
        ORDER BY ingredients.name
    """, (location_id,))

    return [
        TextContent(
            type="text",
            text=str(rows),
        )
    ]


# --------------------------------------------------
# Get Recipe Allergens
# --------------------------------------------------
def handle_get_recipe_allergens(arguments: dict):
    """
    Return all allergens contained
    in a menu item.
    """

    item_id = arguments["item_id"]

    validate_recipe_item_id(item_id)

    rows = execute_query("""
        SELECT DISTINCT
            ingredients.allergen_tags
        FROM recipe_ingredients
        JOIN ingredients
            ON recipe_ingredients.ingredient_id =
               ingredients.ingredient_id
        WHERE recipe_ingredients.item_id = ?
          AND ingredients.allergen_tags <> ''
    """, (item_id,))

    allergens = []

    for row in rows:
        for tag in row["allergen_tags"].split(","):
            tag = tag.strip()
            if tag and tag not in allergens:
                allergens.append(tag)

    return [
        TextContent(
            type="text",
            text=f"Allergens: {', '.join(allergens)}",
        )
    ]