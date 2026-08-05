"""
validation.py

Shared validation helpers for Copperleaf Kitchen's MCP tools.
These functions raise ValueError when validation fails.
"""

from numbers import Number


def validate_positive_integer(value, field_name: str) -> int:
    """Ensure a value is a positive integer."""

    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")

    return value


def validate_positive_number(value, field_name: str) -> float:
    """Ensure a value is a positive number."""

    if not isinstance(value, Number):
        raise ValueError(f"{field_name} must be a number.")

    if value <= 0:
        raise ValueError(f"{field_name} must be greater than 0.")

    return float(value)


def validate_non_empty_string(value, field_name: str) -> str:
    """Ensure a string is not empty."""

    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string.")

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} cannot be empty.")

    return value


# def validate_choice(value, allowed_values, field_name: str):
#     """Ensure a value is one of the allowed options."""

#     if value not in allowed_values:
#         allowed = ", ".join(map(str, allowed_values))
#         raise ValueError(
#             f"{field_name} must be one of: {allowed}"
#         )

#     return value


def validate_quantity(quantity: int) -> int:
    """Validate inventory or purchase quantities."""

    return validate_positive_integer(quantity, "Quantity")


def validate_unit_cost(cost: float) -> float:
    """Validate ingredient unit cost."""

    return validate_positive_number(cost, "Unit cost")


def validate_location_id(location_id: int) -> int:
    """Validate restaurant location IDs."""

    return validate_positive_integer(location_id, "Location ID")


def validate_supplier_id(supplier_id: int) -> int:
    """Validate supplier IDs."""

    return validate_positive_integer(supplier_id, "Supplier ID")


def validate_staff_id(staff_id: int) -> int:
    """Validate staff IDs."""

    return validate_positive_integer(staff_id, "Staff ID")


def validate_purchase_order_id(order_id: int) -> int:
    """Validate purchase order IDs."""

    return validate_positive_integer(order_id, "Purchase Order ID")


def validate_ingredient_id(ingredient_id: int) -> int:
    """Validate ingredient IDs."""

    return validate_positive_integer(
        ingredient_id,
        "Ingredient ID",
    )


def validate_recipe_item_id(item_id: int) -> int:
    """Validate menu item IDs."""

    return validate_positive_integer(
        item_id,
        "Menu Item ID",
    )