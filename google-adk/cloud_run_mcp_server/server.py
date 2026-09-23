"""Demo #5: a standalone MCP server exposing read-only Cloud Run fleet tools.

This is NOT an ADK agent - there's no `adk create`/`adk run` for it. It's a
plain Python program using the `mcp` SDK's FastMCP helper, run directly with
`python server.py`, and it's the thing `ops_agent` connects to over
Streamable HTTP.

Two tools, both read-only on purpose - see Workshop 3's "Read-Only Tools by
Default" section for why a server reachable by any authenticated MCP client
should never expose destructive operations:
    - list_cloud_run_services: what's deployed, and where
    - get_service_logs: recent log lines for one service

Run it locally:
    export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
    python server.py
Then poke it directly with the MCP Inspector, no agent required:
    npx @modelcontextprotocol/inspector http://localhost:8080/mcp
"""
import os

from google.cloud import logging as gcp_logging
from google.cloud import run_v2
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("cloud-run-ops")


@mcp.tool()
def list_cloud_run_services(region: str = "us-central1") -> dict:
    """List Cloud Run services currently deployed in this project and region.

    Args:
        region: GCP region to search, e.g. "us-central1".

    Returns:
        On success: {"status": "ok", "services": [{"name", "url", "last_deployed"}]}
        On failure: {"status": "error", "error_message": "<details>"}
    """
    try:
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        client = run_v2.ServicesClient()
        parent = f"projects/{project}/locations/{region}"
        services = [
            {
                "name": svc.name.rsplit("/", 1)[-1],
                "url": svc.uri,
                "last_deployed": svc.update_time.isoformat() if svc.update_time else None,
            }
            for svc in client.list_services(parent=parent)
        ]
        return {"status": "ok", "services": services}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


@mcp.tool()
def get_service_logs(service_name: str, limit: int = 20) -> dict:
    """Return the most recent log lines for a given Cloud Run service.

    Args:
        service_name: Cloud Run service name, e.g. "adk-default-service-name".
        limit: Max number of log entries to return (default 20, capped at 50).

    Returns:
        On success: {"status": "ok", "service": "<name>", "logs": ["<line>", ...]}
        On failure: {"status": "error", "error_message": "<details>"}
    """
    try:
        limit = min(limit, 50)
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        client = gcp_logging.Client(project=project)
        log_filter = (
            f'resource.type="cloud_run_revision" '
            f'resource.labels.service_name="{service_name}"'
        )
        entries = client.list_entries(filter_=log_filter, order_by=gcp_logging.DESCENDING, max_results=limit)
        lines = [str(entry.payload) for entry in entries]
        return {"status": "ok", "service": service_name, "logs": lines}
    except Exception as e:
        return {"status": "error", "error_message": str(e)}


if __name__ == "__main__":
    # Cloud Run injects the port to listen on via $PORT - respect it, or
    # this container fails Cloud Run's startup health check.
    mcp.run(transport="streamable-http", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
