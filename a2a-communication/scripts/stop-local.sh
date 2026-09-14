#!/usr/bin/env bash
# Kills the three locally-started demo agents. Uses both the PID file and a
# port-based pkill fallback, since `uv run` (Python agents) and `node` (the
# hotel agent) both spawn child processes that can survive killing the wrapper.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"

declare -A PORTS=(
  [flight-search-agent]=8001
  [hotel-search-agent]=8002
  [travel-orchestrator]=8000
)

# hotel-search-agent runs as `node src/index.js`, the other two as uvicorn -
# match each one's actual process pattern for the fallback kill.
declare -A KILL_PATTERNS=(
  [flight-search-agent]="uvicorn app.fast_api_app:app --host 0.0.0.0 --port"
  [hotel-search-agent]="node src/index.js"
  [travel-orchestrator]="uvicorn app.fast_api_app:app --host 0.0.0.0 --port"
)

for name in "${!PORTS[@]}"; do
  port="${PORTS[$name]}"
  pid_file="$LOG_DIR/$name.pid"
  if [[ -f "$pid_file" ]]; then
    pid="$(cat "$pid_file")"
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$pid_file"
  fi
  pkill -9 -f "${KILL_PATTERNS[$name]}" 2>/dev/null || true
  echo "Stopped $name (port $port)"
done
