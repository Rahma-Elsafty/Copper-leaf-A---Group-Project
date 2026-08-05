"""
auth.py

Role-based authorization helpers for the Copperleaf MCP Server.
These functions determine whether a staff member is allowed to
perform specific actions.
"""

from mcp_server.database import execute_query


def get_staff_member(staff_id: int):
    """
    Return the staff record for the given staff ID.
    """

    rows = execute_query(
        """
        SELECT
            staff_id,
            name,
            role,
            location_id
        FROM staff
        WHERE staff_id = ?
        """,
        (staff_id,),
    )

    return rows[0] if rows else None


def get_staff_role(staff_id: int) -> str | None:
    """
    Return the staff member's role.
    """

    staff = get_staff_member(staff_id)

    if not staff:
        return None

    return staff["role"]


def is_line_cook(staff_id: int) -> bool:
    """
    Check whether the staff member is a line cook.
    """

    return get_staff_role(staff_id) == "line_cook"


def is_kitchen_manager(staff_id: int) -> bool:
    """
    Check whether the staff member is a kitchen manager.
    """

    return get_staff_role(staff_id) == "kitchen_manager"


def is_food_safety_officer(staff_id: int) -> bool:
    """
    Check whether the staff member is a food safety officer.
    """

    return get_staff_role(staff_id) == "food_safety_officer"


def require_kitchen_manager(staff_id: int):
    """
    Raise an error unless the staff member is a kitchen manager.
    """

    if not is_kitchen_manager(staff_id):
        raise PermissionError(
            "Only kitchen managers may perform this action."
        )


def require_food_safety_officer(staff_id: int):
    """
    Raise an error unless the staff member is a food safety officer.
    """

    if not is_food_safety_officer(staff_id):
        raise PermissionError(
            "Only food safety officers may perform this action."
        )


def require_staff_member(staff_id: int):
    """
    Ensure the staff member exists.
    """

    if get_staff_member(staff_id) is None:
        raise ValueError("Staff member not found.")