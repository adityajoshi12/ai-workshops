# ops_agent

An ADK agent with zero tool code of its own - `fleet_tools` is an
`McpToolset` that connects to [`../cloud_run_mcp_server/`](../cloud_run_mcp_server/)
over Streamable HTTP and expands into whatever tools that server advertises.

## Run it locally

Start `cloud_run_mcp_server` in another terminal first, then:

```bash
export MCP_SERVER_URL="http://localhost:8080/mcp"
adk web
```

Pick `ops_agent` and ask: *"What Cloud Run services are deployed in this project?"*

## Deploy to Cloud Run

```bash
adk deploy cloud_run ops_agent -- \
  --region=us-central1 \
  --set-env-vars=MCP_SERVER_URL="https://mcp-server-XXXXXXXXXX.us-central1.run.app/mcp",GOOGLE_API_KEY=YOUR_GEMINI_API_KEY,GOOGLE_GENAI_USE_VERTEXAI=FALSE
```

This agent's runtime service account needs `roles/run.invoker` on
`mcp-server` - `agent.py` mints a Google-signed ID token per process start
and sends it as the `Authorization` header automatically (skipped for a
`localhost` URL, so local dev needs no auth setup). Full walkthrough in
[Workshop 3](../workshop-3-mcp-cloud-run/README.md).
