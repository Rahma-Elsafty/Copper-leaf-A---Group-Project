Libs Used:
mcp[cli]         # Official MCP SDK + FastMCP + CLI tools for testing/debugging (Done)
sqlalchemy       # ORM for interacting with the restaurant database
aiosqlite        # Async SQLite database driver
pydantic         # Input validation and tool schemas
python-dotenv    # Load environment variables from a .env file
loguru           # Better logging while developing
rich             # Pretty terminal output and tracebacks
pytest           # Unit testing your MCP tools
fastapi          # HTTP server for the production transport
uvicorn          # Runs the FastAPI application

-------------
1. validation.py      
2. auth.py            
3. tools_read.py
4. tools_write.py
5. tools_progress.py
6. resources.py
7. prompts.py
8. notifications.py
9. server.py
10. client.py
-----------
INSPECTION: npx @modelcontextprotocol/inspector python -m mcp_server.server