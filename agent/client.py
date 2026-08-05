import asyncio

from mcp.client import ClientSession
from mcp.client.stdio import (
    stdio_client,
    StdioServerParameters,
)


async def main():

    server = StdioServerParameters(
        command="python",
        args=["-m", "mcp_server.server"],
    )

    async with stdio_client(server) as (read_stream, write_stream):

        async with ClientSession(read_stream, write_stream) as session:

            print("Initializing...")

            await session.initialize()

            print("Connected!")

            while True:

                print("\n===================================")
                print("      Copperleaf MCP Client")
                print("===================================")
                print("1. List Tools")
                print("2. List Resources")
                print("3. List Prompts")
                print("4. Call Tool")
                print("5. Read Resource")
                print("6. Get Prompt")
                print("7. Exit")

                choice = input("\nChoice: ").strip()

                # ---------------------------------
                # List Tools
                # ---------------------------------
                if choice == "1":

                    tools = await session.list_tools()

                    print("\nAvailable Tools:\n")

                    for tool in tools.tools:
                        print(f"• {tool.name}")

                # ---------------------------------
                # List Resources
                # ---------------------------------
                elif choice == "2":

                    resources = await session.list_resources()

                    print("\nAvailable Resources:\n")

                    for resource in resources.resources:
                        print(f"• {resource.name}")
                        print(f"  URI: {resource.uri}")
                        print()

                # ---------------------------------
                # List Prompts
                # ---------------------------------
                elif choice == "3":

                    prompts = await session.list_prompts()

                    print("\nAvailable Prompts:\n")

                    for prompt in prompts.prompts:
                        print(f"• {prompt.name}")
                        print(f"  {prompt.description}")
                        print()

                # ---------------------------------
                # Call Tool
                
                elif choice == "4":

                    # Get all available tools
                    tools = await session.list_tools()

                    print("\nAvailable Tools:\n")
                    for tool in tools.tools:
                        print(f"• {tool.name}")

                    tool_name = input("\nTool name: ").strip()

                    # Find the selected tool
                    selected_tool = None
                    for tool in tools.tools:
                        if tool.name == tool_name:
                            selected_tool = tool
                            break

                    if selected_tool is None:
                        print("\nTool not found.")
                        continue

                    arguments = {}

                    # MCP 2.0 uses input_schema
                    schema = selected_tool.input_schema or {}

                    required = schema.get("required", [])
                    properties = schema.get("properties", {})

                    if required:
                        print("\nEnter arguments:\n")

                    for arg in required:

                        arg_type = properties.get(arg, {}).get("type", "string")

                        value = input(f"{arg} ({arg_type}): ")

                        if arg_type == "integer":
                            value = int(value)
                        elif arg_type == "number":
                            value = float(value)
                        elif arg_type == "boolean":
                            value = value.lower() in ("true", "1", "yes")

                        arguments[arg] = value

                    result = await session.call_tool(
                        tool_name,
                        arguments,
                    )

                    print("\nResult:\n")

                    for item in result.content:
                        print(item.text)
                # ---------------------------------
                # Read Resource
                # ---------------------------------
                elif choice == "5":

                    uri = input("Resource URI: ").strip()

                    result = await session.read_resource(uri)

                    print()

                    for item in result.contents:
                        print(item.text)

                # ---------------------------------
                # Get Prompt
                # ---------------------------------
                elif choice == "6":

                    prompt_name = input("Prompt name: ").strip()

                    result = await session.get_prompt(prompt_name)

                    print()

                    print(result.description)
                    print("-" * 40)

                    for message in result.messages:
                        print(message.content.text)

                # ---------------------------------
                # Exit
                # ---------------------------------
                elif choice == "7":

                    print("\nGoodbye!")
                    break

                else:

                    print("\nInvalid choice.")


if __name__ == "__main__":
    asyncio.run(main())
