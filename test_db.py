from mcp_server.database import execute_query

rows = execute_query("SELECT * FROM suppliers")

print(f"Found {len(rows)} suppliers\n")

for supplier in rows:
    print(dict(supplier))