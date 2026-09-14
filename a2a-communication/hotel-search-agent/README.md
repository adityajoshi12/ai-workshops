# hotel-search-agent

A2A hotel search agent built on **LangGraph.js** (LangChain's JS agent
framework) and the **official `@a2a-js/sdk`** - not ADK, not Python. It's the
one agent in this demo that proves A2A interop across *language* boundaries,
not just cloud platforms: `travel-orchestrator`'s ADK `RemoteA2aAgent` calls
this agent the exact same way it calls the ADK-based `flight-search-agent` -
over plain JSON-RPC, with zero knowledge of what's on the other end.

Deploy target: a **bare Compute Engine VM**, on purpose - no managed platform,
just a container on a box, to show the protocol doesn't need one.

## Project structure

```
hotel-search-agent/
  src/
    tools.js       # search_hotels mock tool (deterministic fake data)
    agent.js       # LangGraph.js agent: langchain's createAgent() + Vertex AI
    agentCard.js   # A2A AgentCard served at /a2a/app/.well-known/agent-card.json
    executor.js    # Bridges A2A task/event lifecycle to the LangGraph agent
    index.js       # Express app - mounts the A2A JSON-RPC + card routes
  test/
    tools.test.js  # node:test - pure logic, no network/LLM calls
```

## Requirements

- Node.js 22+
- `gcloud` CLI, authenticated with ADC (`gcloud auth application-default login`)
- A GCP project with the Vertex AI API enabled and Gemini model access granted

## Local development

```bash
npm install
cp .env.example .env   # then fill in GOOGLE_CLOUD_PROJECT
npm start               # listens on :8080 by default
npm test                 # runs the tool unit tests, no network needed
```

Check the agent card:

```bash
curl http://localhost:8080/a2a/app/.well-known/agent-card.json | jq .
```

`APP_URL` controls the URL baked into the agent card's `supportedInterfaces` -
set it to wherever this instance is externally reachable (`http://localhost:8080`
locally, `http://<vm-external-ip>:8080` once deployed). If it's wrong, other
agents will resolve the card fine but fail to actually call you.

## Why `createAgent`, not `createReactAgent`

`@langchain/langgraph/prebuilt`'s `createReactAgent` is deprecated in the
currently published SDK version in favor of `createAgent` from the `langchain`
package itself - same ReAct loop, current API. This agent uses the
non-deprecated one.

## Deployment

See the root `README.md`'s "hotel-search-agent -> Compute Engine VM" section
for the full `gcloud builds submit` + `gcloud compute instances create`
(Container-Optimized OS) sequence. The container listens on `8080` and needs at
minimum `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, and `APP_URL` (set to
the VM's external IP) as env vars.

## Mock data disclaimer

`search_hotels` returns three fictional hotels with deterministically-seeded
fake prices/ratings (same city + dates always return the same numbers, for a
believable demo). No real hotels, no booking capability, no external API
calls beyond Vertex AI for the LLM reasoning itself.
