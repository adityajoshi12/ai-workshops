#!/usr/bin/env bash
# =============================================================================
# start.sh — Start MCP demo infrastructure (Keycloak + MCP Server + AgentGateway)
#
# After this script prints "Ready", run the agent in another terminal:
#
#   python3 agent_demo.py --client-id agent-core-client --client-secret <printed-secret>
#
# Flags:
#   --keep   Reuse the existing Keycloak container (skip fresh setup)
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

DOCKER="$(which docker || which podman)"
PYTHON="$(which python || which python3)"
AGENTGW="$(which agentgateway)"
KEEP_KC=false
[[ "${1:-}" == "--keep" ]] && KEEP_KC=true

GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
banner() { echo -e "\n${CYAN}▶ $*${NC}"; }
info()   { echo -e "${GREEN}  ✓${NC} $*"; }

# ─── Kill any leftover processes ──────────────────────────────────────────────
pkill -f "server\.py"  2>/dev/null || true
pkill -f "agentgateway" 2>/dev/null || true
sleep 1

# ─── Step 1: Keycloak ─────────────────────────────────────────────────────────
banner "Step 1/4 — Keycloak"
if $KEEP_KC; then
  if $DOCKER ps -q --filter name=keycloak | grep -q .; then
    info "Reusing running Keycloak container"
  else
    info "Restarting stopped Keycloak container"
    $DOCKER start keycloak > /dev/null
  fi
else
  $DOCKER rm -f keycloak 2>/dev/null || true
  $DOCKER run -d --name keycloak \
    -p 8080:8080 \
    -p 8081:9000 \
    -e KEYCLOAK_ADMIN=admin \
    -e KEYCLOAK_ADMIN_PASSWORD=admin \
    -e KC_HEALTH_ENABLED="true" \
    quay.io/keycloak/keycloak:latest start-dev > /dev/null
  info "Keycloak container started (port 8080)"
fi

# ─── Step 2: Configure realm / clients ────────────────────────────────────────
banner "Step 2/4 — Keycloak realm + clients"
bash setup_keycloak.sh
source .demo-secrets
info "Realm ai-mesh ready"

# ─── Step 3: MCP Server ───────────────────────────────────────────────────────
banner "Step 3/4 — MCP Server"
$PYTHON server.py > mcp_server.log 2>&1 &
MCP_PID=$!
sleep 2
kill -0 "$MCP_PID" 2>/dev/null || { echo "ERROR: MCP server failed"; cat mcp_server.log; exit 1; }
info "MCP server on port 9000  (PID $MCP_PID)"

# ─── Step 4: AgentGateway ─────────────────────────────────────────────────────
banner "Step 4/4 — AgentGateway"
$AGENTGW -f config.yaml > agentgateway.log 2>&1 &
GW_PID=$!
sleep 3
kill -0 "$GW_PID" 2>/dev/null || { echo "ERROR: AgentGateway failed"; cat agentgateway.log; exit 1; }
info "AgentGateway on port 3000  (PID $GW_PID)"

# ─── Print ready banner ───────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║     All Services Ready — Open a NEW terminal          ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════╝${NC}"
echo ""
echo "  Keycloak UI:  http://localhost:8080  (admin / admin)"
echo "  AgentGateway: http://localhost:3000/mcp"
echo "  MCP Server:   http://localhost:9000/sse"
echo ""
echo -e "${BOLD}── READER agent (gets BLOCKED on delete) ──────────────────${NC}"
echo "  $PYTHON agent_demo.py \\"
echo "    --client-id $READER_CLIENT_ID \\"
echo "    --client-secret $READER_SECRET"
echo ""
echo -e "${BOLD}── ADMIN agent (delete is ALLOWED) ────────────────────────${NC}"
echo "  $PYTHON agent_demo.py \\"
echo "    --client-id $ADMIN_CLIENT_ID \\"
echo "    --client-secret $ADMIN_SECRET"
echo ""
echo -e "${YELLOW}  This terminal is holding the services. Ctrl+C to stop.${NC}"
wait "$GW_PID"
