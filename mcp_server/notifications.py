"""
notifications.py

Helper functions for creating consistent notification messages
used by MCP tools.
"""


def success(message: str) -> str:
    """
    Return a success notification.
    """
    return f"SUCCESS: {message}"


def warning(message: str) -> str:
    """
    Return a warning notification.
    """
    return f"WARNING: {message}"


def error(message: str) -> str:
    """
    Return an error notification.
    """
    return f"ERROR: {message}"


def info(message: str) -> str:
    """
    Return an informational notification.
    """
    return f"INFO: {message}"


# def budget_warning(remaining_budget: float) -> str:
#     """
#     Warning shown when a purchase order exceeds 80%
#     of the remaining monthly budget.
#     """
#     return (
#         f"WARNING: This purchase order exceeds 80% of the "
#         f"remaining monthly budget (${remaining_budget:.2f} remaining). "
#         "Human confirmation is required."
#     )


def supplier_warning(supplier_name: str) -> str:
    """
    Warning shown when a supplier has not yet been verified.
    """
    return (
        f"WARNING: Supplier '{supplier_name}' is not verified. "
        "Human confirmation is required before continuing."
    )


# def audit_complete(items_checked: int) -> str:
#     """
#     Notification after completing an inventory audit.
#     """
#     return (
#         f"SUCCESS: Inventory audit completed. "
#         f"{items_checked} inventory items were checked."
#     )


def purchase_order_created(po_id: int) -> str:
    """
    Notification after creating a purchase order.
    """
    return (
        f"SUCCESS: Purchase Order #{po_id} created successfully."
    )


def supplier_verified(supplier_name: str) -> str:
    """
    Notification after verifying a supplier.
    """
    return (
        f"SUCCESS: Supplier '{supplier_name}' has been verified."
    )