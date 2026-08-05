import asyncio
import sys

import mcp.server.stdio
import mcp.types as types
from mcp.server import ServerRequestContext
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

from mcp_server.tools_read import (
    handle_list_suppliers,
    handle_get_supplier,
    handle_list_low_stock_items,
    handle_get_recipe_allergens,
)

from mcp_server.tools_write import (
    place_purchase_order,
    approve_purchase_order,
    mark_supplier_verified,
    record_inventory_count,
)

from mcp_server.resources import (
    list_safety_policies,
    get_safety_policy,
    list_supplier_resources,
    get_supplier_resource,
    list_open_incidents,
    get_incident,
)
from mcp_server.prompts import (
    health_inspection_report,
)

# -------------------------
# Tools
# -------------------------
async def on_list_tools(
    context: ServerRequestContext,
    params,
) -> types.ListToolsResult:

    return types.ListToolsResult(
    tools=[

        types.Tool(
            name="list_suppliers",
            description="Return all suppliers.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),

        types.Tool(
            name="get_supplier",
            description="Return a supplier by ID.",
            inputSchema={
                "type": "object",
                "properties":{
                    "supplier_id":{"type":"integer"}
                },
                "required":["supplier_id"]
            },
        ),

        types.Tool(
            name="list_low_stock_items",
            description="Return ingredients below reorder threshold.",
            inputSchema={
                "type":"object",
                "properties":{
                    "location_id":{"type":"integer"}
                },
                "required":["location_id"]
            },
        ),

        types.Tool(
            name="get_recipe_allergens",
            description="Return allergens for a menu item.",
            inputSchema={
                "type":"object",
                "properties":{
                    "item_id":{"type":"integer"}
                },
                "required":["item_id"]
            },
        ),

        types.Tool(
            name="place_purchase_order",
            description="Create a purchase order.",
            inputSchema={
                "type":"object",
                "properties":{
                    "ingredient_id":{"type":"integer"},
                    "supplier_id":{"type":"integer"},
                    "qty":{"type":"integer"},
                    "unit_cost":{"type":"number"},
                    "requested_by":{"type":"integer"}
                },
                "required":[
                    "ingredient_id",
                    "supplier_id",
                    "qty",
                    "unit_cost",
                    "requested_by"
                ]
            },
        ),

        types.Tool(
            name="approve_purchase_order",
            description="Approve a purchase order.",
            inputSchema={
                "type":"object",
                "properties":{
                    "po_id":{"type":"integer"}
                },
                "required":["po_id"]
            },
        ),

        types.Tool(
            name="mark_supplier_verified",
            description="Verify a supplier.",
            inputSchema={
                "type":"object",
                "properties":{
                    "supplier_id":{"type":"integer"}
                },
                "required":["supplier_id"]
            },
        ),

        types.Tool(
            name="record_inventory_count",
            description="Update inventory quantity.",
            inputSchema={
                "type":"object",
                "properties":{
                    "stock_id":{"type":"integer"},
                    "quantity":{"type":"integer"}
                },
                "required":["stock_id","quantity"]
            },
        ),
    ]
)


async def on_call_tool(
    context: ServerRequestContext,
    params: types.CallToolRequestParams,
):

    if params.name == "list_suppliers":
        return types.CallToolResult(
        content=handle_list_suppliers({})
    )

    elif params.name == "get_supplier":
        return types.CallToolResult(
            content=handle_get_supplier(params.arguments)
        )

    elif params.name == "list_low_stock_items":
        return types.CallToolResult(
            content=handle_list_low_stock_items(params.arguments)
        )

    elif params.name == "get_recipe_allergens":
        return types.CallToolResult(
            content=handle_get_recipe_allergens(params.arguments)
        )
    elif params.name == "place_purchase_order":

        result = place_purchase_order(
            **params.arguments
        )

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=str(result),
                )
            ]
        )
    elif params.name == "approve_purchase_order":

        result = approve_purchase_order(
            **params.arguments
        )

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=str(result),
                )
            ]
        )

    elif params.name == "mark_supplier_verified":

        result = mark_supplier_verified(
            **params.arguments
        )

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=str(result),
                )
            ]
        )

    elif params.name == "record_inventory_count":

        result = record_inventory_count(
            **params.arguments
        )

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=str(result),
                )
            ]
        )

    else:
        raise ValueError(f"Unknown tool: {params.name}")
    

# -------------------------
# Resources
# -------------------------
async def on_list_resources(
    context: ServerRequestContext,
    params,
) -> types.ListResourcesResult:

    return types.ListResourcesResult(
        resources=[
            types.Resource(
                name="Safety Policies",
                uri="resource://policies",
                description="List of all food safety policies.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Safety Policy",
                uri="resource://policy/{id}",
                description="A single safety policy.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Suppliers",
                uri="resource://suppliers",
                description="List of all suppliers.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Supplier",
                uri="resource://supplier/{id}",
                description="A single supplier.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Open Incidents",
                uri="resource://incidents",
                description="List of all open food safety incidents.",
                mimeType="application/json",
            ),
            types.Resource(
                name="Incident",
                uri="resource://incident/{id}",
                description="A single food safety incident.",
                mimeType="application/json",
            ),
        ]
    )


async def on_read_resource(
    context: ServerRequestContext,
    params: types.ReadResourceRequestParams,
):

    uri = str(params.uri)

    # -------------------------
    # Suppliers
    # -------------------------
    if uri == "resource://suppliers":

        data = list_supplier_resources()

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=str(data),
                )
            ]
        )

    elif uri.startswith("resource://supplier/"):

        supplier_id = int(uri.split("/")[-1])

        supplier = get_supplier_resource(supplier_id)

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=str(supplier),
                )
            ]
        )

    # -------------------------
    # Safety Policies
    # -------------------------
    elif uri == "resource://policies":

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=str(list_safety_policies()),
                )
            ]
        )

    elif uri.startswith("resource://policy/"):

        policy_id = int(uri.split("/")[-1])

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=str(get_safety_policy(policy_id)),
                )
            ]
        )

    # -------------------------
    # Open Incidents
    # -------------------------
    elif uri == "resource://incidents":

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=str(list_open_incidents()),
                )
            ]
        )

    elif uri.startswith("resource://incident/"):

        incident_id = int(uri.split("/")[-1])

        return types.ReadResourceResult(
            contents=[
                types.TextResourceContents(
                    uri=uri,
                    mimeType="application/json",
                    text=str(get_incident(incident_id)),
                )
            ]
        )

    raise ValueError(f"Unknown resource: {uri}")

# -------------------------
# Prompts
# -------------------------
# -------------------------
# Prompts
# -------------------------
async def on_list_prompts(
    context: ServerRequestContext,
    params,
) -> types.ListPromptsResult:

    print(">>> on_list_prompts called", file=sys.stderr)

    return types.ListPromptsResult(
        prompts=[
            types.Prompt(
                name="health_inspection_report",
                description="Generate a health inspection report.",
            ),
        ]
    )


async def on_get_prompt(
    context: ServerRequestContext,
    params: types.GetPromptRequestParams,
) -> types.GetPromptResult:

    print(f">>> on_get_prompt called: {params.name}", file=sys.stderr)

    if params.name == "health_inspection_report":
        text = health_inspection_report()
    else:
        raise ValueError(f"Unknown prompt: {params.name}")

    return types.GetPromptResult(
        description="Health Inspection Report",
        messages=[
            types.PromptMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=text,
                ),
            )
        ],
    )


# -------------------------
# Server
# -------------------------
server = Server(
    "Copperleaf-MCP-Server",
    version="1.0.0",
    on_list_tools=on_list_tools,
    on_call_tool=on_call_tool,
    on_list_resources=on_list_resources,
    on_read_resource=on_read_resource,
    on_list_prompts=on_list_prompts,
    on_get_prompt=on_get_prompt,
)

print("\n========== REGISTERED REQUEST HANDLERS ==========", file=sys.stderr)
for method in sorted(server._request_handlers.keys()):
    print(method, file=sys.stderr)
print("=================================================\n", file=sys.stderr)


# -------------------------
# Run Server
# -------------------------
async def run():

    caps = server.get_capabilities(
        notification_options=NotificationOptions(),
        experimental_capabilities={},
    )

    print("\n========== SERVER CAPABILITIES ==========", file=sys.stderr)
    print(caps, file=sys.stderr)
    print("=========================================\n", file=sys.stderr)

    async with mcp.server.stdio.stdio_server() as (
        read_stream,
        write_stream,
    ):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="Copperleaf-MCP-Server",
                server_version="1.0.0",
                capabilities=caps,
            ),
        )


if __name__ == "__main__":
    asyncio.run(run())     
