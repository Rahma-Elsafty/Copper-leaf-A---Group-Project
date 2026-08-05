from mcp_server.database import execute_query


# --------------------------------------------------
# Safety Policies
# --------------------------------------------------

def list_safety_policies():
    """
    Return all available safety policies.
    """

    return execute_query("""
        SELECT
            policy_id,
            title
        FROM safety_policies
        ORDER BY policy_id
    """)


def get_safety_policy(policy_id: int):
    """
    Return a single safety policy.
    """

    rows = execute_query("""
        SELECT
            policy_id,
            title,
            doc_text
        FROM safety_policies
        WHERE policy_id = ?
    """, (policy_id,))

    if rows:
        return rows[0]

    return None


# --------------------------------------------------
# Suppliers (Read-Only Resources)
# --------------------------------------------------

def list_supplier_resources():
    """
    Return all suppliers as read-only resources.
    """

    return execute_query("""
        SELECT
            supplier_id,
            name,
            verified,
            contact
        FROM suppliers
        ORDER BY name
    """)


def get_supplier_resource(supplier_id: int):
    """
    Return a single supplier resource.
    """

    rows = execute_query("""
        SELECT
            supplier_id,
            name,
            verified,
            contact
        FROM suppliers
        WHERE supplier_id = ?
    """, (supplier_id,))

    if rows:
        return rows[0]

    return None


# --------------------------------------------------
# Food Safety Incidents (Read-Only)
# --------------------------------------------------

def list_open_incidents():
    """
    Return all currently open food safety incidents.
    """

    return execute_query("""
        SELECT
            incident_id,
            location_id,
            type,
            status,
            summary,
            created_at
        FROM food_safety_incidents
        WHERE status = 'open'
        ORDER BY created_at DESC
    """)


def get_incident(incident_id: int):
    """
    Return a single food safety incident.
    """

    rows = execute_query("""
        SELECT
            incident_id,
            location_id,
            type,
            opened_by,
            status,
            summary,
            created_at
        FROM food_safety_incidents
        WHERE incident_id = ?
    """, (incident_id,))

    if rows:
        return rows[0]

    return None
