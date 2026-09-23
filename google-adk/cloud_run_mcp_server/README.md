# cloud_run_mcp_server

A standalone MCP server - not an ADK agent - exposing two read-only tools
over Streamable HTTP for `ops_agent` (or any other MCP client) to call:

- `list_cloud_run_services(region)` - what's deployed and where
- `get_service_logs(service_name, limit)` - recent log lines for one service

## Run it locally

```bash
export GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
pip install -r requirements.txt
python server.py
```

Test it directly, no agent required:

```bash
npx @modelcontextprotocol/inspector http://localhost:8080/mcp
```

## Deploy to Cloud Run

Deployed **without** `--allow-unauthenticated` on purpose - see
[Workshop 3](../workshop-3-mcp-cloud-run/README.md) for the full
service-to-service auth setup (`roles/run.invoker` between this service and
`ops_agent`).

```bash
gcloud run deploy mcp-server \
  --source . \
  --region=us-central1 \
  --no-allow-unauthenticated \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
```

Its runtime service account needs `roles/run.viewer` and
`roles/logging.viewer` on the project to actually answer either tool.
