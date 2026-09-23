"""Demo #5: an ADK agent whose tools live in a separate MCP server.

Unlike every other demo in this workshop repo, this agent has zero tool
code of its own - `fleet_tools` is an MCPToolset that connects to
`cloud_run_mcp_server/server.py` over Streamable HTTP and expands into
whatever tools that server advertises at connection time. Add a tool to the
server, and this agent picks it up with no code change here.

Run it locally (server must already be running - see
`cloud_run_mcp_server/server.py`'s docstring):
    export MCP_SERVER_URL="http://localhost:8080/mcp"
    adk web

Deployed to Cloud Run, MCP_SERVER_URL points at the deployed mcp-server
instead, and this agent mints a Google-signed ID token scoped to that URL
on every process start so the two services authenticate to each other
without a shared secret. See Workshop 3's "Authenticate Service-to-Service"
step for the `roles/run.invoker` binding this depends on.
"""
import os

from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPServerParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset

MODEL = "gemini-3.5-flash"
MCP_SERVER_URL = os.environ.get("MCP_SERVER_URL", "http://localhost:8080/mcp")


def _mcp_connection_headers(url: str) -> dict:
    """Attach a Google-signed ID token, except when talking to a local server.

    A local `python server.py` has no IAM in front of it, so skipping auth
    keeps local dev friction-free. Anything else is assumed to be a Cloud
    Run URL that requires roles/run.invoker to reach.
    """
    if url.startswith("http://localhost") or url.startswith("http://127.0.0.1"):
        return {}
    import google.auth.transport.requests
    import google.oauth2.id_token

    audience = url.rsplit("/mcp", 1)[0]
    auth_request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(auth_request, audience)
    return {"Authorization": f"Bearer {token}"}


fleet_tools = McpToolset(
    connection_params=StreamableHTTPServerParams(
        url=MCP_SERVER_URL,
        headers=_mcp_connection_headers(MCP_SERVER_URL),
    ),
)

root_agent = Agent(
    model=MODEL,
    name="cloud_run_ops_agent",
    description="Answers questions about the Cloud Run services deployed in this project.",
    instruction=(
        "You are an SRE assistant for a Google Cloud project. Use "
        "list_cloud_run_services to see what is deployed, and "
        "get_service_logs to inspect recent activity for one service. "
        "Never guess a service's URL, deploy time, or log contents - "
        "always call a tool. If a tool returns status 'error', explain "
        "the error to the user in plain language instead of retrying blindly."
    ),
    tools=[fleet_tools],
)
