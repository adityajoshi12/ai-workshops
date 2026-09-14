#!/usr/bin/env bash
# Starts all three A2A demo agents locally on separate ports for a dry run
# before touching the cloud. Logs go to ./logs/*.log, PIDs to ./logs/*.pid.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# hotel-search-agent runs on Node/LangGraph.js, the other two on Python/ADK -
# each gets started with its own runtime's native command.
start_python_agent() {
  local name="$1" dir="$2" port="$3"
  shift 3
  echo "Starting $name on :$port ..."
  (cd "$dir" && env "$@" uv run uvicorn app.fast_api_app:app --host 0.0.0.0 --port "$port" \
    > "$LOG_DIR/$name.log" 2>&1 &
    echo $! > "$LOG_DIR/$name.pid")
}

start_node_agent() {
  local name="$1" dir="$2" port="$3"
  shift 3
  echo "Starting $name on :$port ..."
  (cd "$dir" && env "$@" PORT="$port" APP_URL="http://localhost:$port" node src/index.js \
    > "$LOG_DIR/$name.log" 2>&1 &
    echo $! > "$LOG_DIR/$name.pid")
}

start_python_agent flight-search-agent "$ROOT_DIR/flight-search-agent" 8001
start_node_agent    hotel-search-agent  "$ROOT_DIR/hotel-search-agent"  8002

sleep 2

start_python_agent travel-orchestrator "$ROOT_DIR/travel-orchestrator" 8000 \
  FLIGHT_AGENT_URL=http://localhost:8001 HOTEL_AGENT_URL=http://localhost:8002

sleep 2
echo ""
echo "All three agents starting up. Tail logs with: tail -f logs/*.log"
echo "  flight-search-agent : http://localhost:8001"
echo "  hotel-search-agent  : http://localhost:8002"
echo "  travel-orchestrator : http://localhost:8000"
echo ""
echo "Run ./scripts/test-local.sh once they're warm, and ./scripts/stop-local.sh when done."
