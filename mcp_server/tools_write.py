from mcp_server.database import execute_query, execute_update

from mcp_server.validation import (
    validate_ingredient_id,
    validate_supplier_id,
    validate_staff_id,
    validate_quantity,
    validate_unit_cost,
)

from mcp_server.auth import (
    require_staff_member,
    require_kitchen_manager,
)

from mcp_server.notifications import (
    purchase_order_created,
    supplier_verified,
    info,
)


# -------------------------------------------------------
# Place Purchase Order
# -------------------------------------------------------

def place_purchase_order(
    ingredient_id,
    supplier_id,
    qty,
    unit_cost,
    requested_by,
):
    """
    Create a new purchase order.

    Only kitchen managers may place purchase orders.
    """

    # ---------- Validation ----------
    validate_ingredient_id(ingredient_id)
    validate_supplier_id(supplier_id)
    validate_staff_id(requested_by)
    validate_quantity(qty)
    validate_unit_cost(unit_cost)

    # ---------- Authorization ----------
    require_staff_member(requested_by)
    require_kitchen_manager(requested_by)

    # ---------- Supplier ----------
    supplier = execute_query(
        """
        SELECT verified
        FROM suppliers
        WHERE supplier_id = ?
        """,
        (supplier_id,),
    )

    if not supplier:
        raise ValueError("Supplier not found.")

    verified = supplier[0]["verified"]

    # ---------- Staff ----------
    staff = execute_query(
        """
        SELECT location_id
        FROM staff
        WHERE staff_id = ?
        """,
        (requested_by,),
    )

    location_id = staff[0]["location_id"]

    # ---------- Budget ----------
    budget = execute_query(
        """
        SELECT monthly_budget
        FROM locations
        WHERE location_id = ?
        """,
        (location_id,),
    )[0]["monthly_budget"]

    committed = execute_query(
        """
        SELECT
            COALESCE(SUM(cost),0) AS total
        FROM purchase_orders
        WHERE requested_by IN (
            SELECT staff_id
            FROM staff
            WHERE location_id = ?
        )
        AND status IN ('pending','approved')
        """,
        (location_id,),
    )[0]["total"]

    remaining_budget = budget - committed

    order_cost = qty * unit_cost

    requires_confirmation = False
    reasons = []

    if order_cost > remaining_budget * 0.80:
        requires_confirmation = True
        reasons.append("Order exceeds 80% of remaining budget.")

    if not verified:
        requires_confirmation = True
        reasons.append("Supplier is not verified.")

    # ---------- Save ----------
    execute_update(
        """
        INSERT INTO purchase_orders
        (
            ingredient_id,
            supplier_id,
            qty,
            cost,
            status,
            requested_by,
            created_at
        )
        VALUES
        (
            ?, ?, ?, ?, ?, ?, datetime('now')
        )
        """,
        (
            ingredient_id,
            supplier_id,
            qty,
            order_cost,
            "pending",
            requested_by,
        ),
    )

    print(info("Purchase order created."))

    return {
        "status": "pending",
        "requires_confirmation": requires_confirmation,
        "reasons": reasons,
        "total_cost": order_cost,
        "remaining_budget": remaining_budget,
    }


# -------------------------------------------------------
# Approve Purchase Order
# -------------------------------------------------------

def approve_purchase_order(po_id):
    """
    Approve an existing purchase order.
    """

    affected = execute_update(
        """
        UPDATE purchase_orders
        SET status='approved'
        WHERE po_id=?
        """,
        (po_id,),
    )

    if affected == 0:
        raise ValueError("Purchase order not found.")

    print(
    info(
        f"Purchase Order #{po_id} approved."
    )
)

    return {
        "status": "approved",
        "purchase_order": po_id,
    }


# -------------------------------------------------------
# Verify Supplier
# -------------------------------------------------------

def mark_supplier_verified(supplier_id):
    """
    Mark a supplier as verified.
    """

    validate_supplier_id(supplier_id)

    affected = execute_update(
        """
        UPDATE suppliers
        SET verified = 1
        WHERE supplier_id = ?
        """,
        (supplier_id,),
    )

    if affected == 0:
        raise ValueError("Supplier not found.")

    print(
    supplier_verified(
        f"Supplier {supplier_id}"
    )
)

    return {
        "verified": True
    }


# -------------------------------------------------------
# Record Inventory Count
# -------------------------------------------------------

def record_inventory_count(
    stock_id,
    quantity,
):
    """
    Update inventory quantity.
    """

    validate_quantity(quantity)

    affected = execute_update(
        """
        UPDATE inventory_stock
        SET qty_on_hand=?
        WHERE stock_id=?
        """,
        (
            quantity,
            stock_id,
        ),
    )

    if affected == 0:
        raise ValueError("Inventory item not found.")

    return {
        "updated": True
    }