from mcp_server.database import execute_query


def list_suppliers():
    rows = execute_query("""
        SELECT
            supplier_id,
            name,
            contact,
            verified
        FROM suppliers
        ORDER BY name
    """)

    return [dict(row) for row in rows]


def get_supplier(supplier_id: int):
    rows = execute_query("""
        SELECT
            supplier_id,
            name,
            contact,
            verified
        FROM suppliers
        WHERE supplier_id = ?
    """, (supplier_id,))

    if rows:
        return dict(rows[0])

    return None