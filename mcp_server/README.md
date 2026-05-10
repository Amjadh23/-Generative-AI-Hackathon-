# RouteIQ MCP Server

This optional wrapper exposes RouteIQ backend capabilities as MCP tools for agent clients.
It does not change the React app or FastAPI API. Start it only when an MCP client needs tools.

## Tools

- `get_day_plan(salesperson_id)`
- `get_top_visits(salesperson_id, limit)`
- `get_customer_profile(customer_id)`
- `explain_customer_score(customer_id)`
- `get_manager_dashboard()`
- `preview_visit_recap(customer_id, salesperson_id, transcript)`

## Run

Install the backend dependencies first, then add the MCP package to the same environment:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r ..\mcp_server\requirements.txt
cd ..
python mcp_server\server.py
```

For AI recap previews, keep Ollama running with the configured model:

```powershell
ollama pull llama3.2:3b
```

The server uses stdio, which is what MCP desktop/agent clients expect.
