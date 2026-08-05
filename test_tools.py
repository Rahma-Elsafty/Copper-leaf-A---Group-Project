from mcp_server.tools import list_suppliers

suppliers = list_suppliers()

print(f"Total suppliers: {len(suppliers)}\n")

for supplier in suppliers:
    print(supplier)