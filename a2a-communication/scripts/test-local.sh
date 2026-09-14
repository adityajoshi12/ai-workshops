#!/usr/bin/env bash
# Sends a trip-planning prompt to the local orchestrator, which should fan
# out to the flight and hotel agents over A2A and combine the results.
set -euo pipefail

PROMPT="${1:-Plan a trip to Austin, Oct 3-5, flying out of SFO}"

echo "Checking AgentCards are up..."
curl -sf http://localhost:8001/a2a/app/.well-known/agent-card.json > /dev/null \
  && echo "  flight-search-agent OK" || echo "  flight-search-agent NOT responding"
curl -sf http://localhost:8002/a2a/app/.well-known/agent-card.json > /dev/null \
  && echo "  hotel-search-agent OK" || echo "  hotel-search-agent NOT responding"

echo ""
echo "Prompt: $PROMPT"
echo ""

(cd "$(dirname "${BASH_SOURCE[0]}")/../travel-orchestrator" && \
  agents-cli run --url http://localhost:8000 --mode a2a "$PROMPT")
