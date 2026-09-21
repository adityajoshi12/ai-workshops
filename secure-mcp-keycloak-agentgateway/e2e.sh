#!/usr/bin/env bash
# =============================================================================
# e2e.sh — End-to-end validation of the MCP + Keycloak security demo
#
# Starts all services, runs both demo scenarios, asserts expected output,
# prints a PASS / FAIL report, then tears everything down.
#
# Usage:
#   ./e2e.sh              # full fresh run
#   ./e2e.sh --keep       # reuse existing Keycloak container
# =============================================================================
set -euo pipefail
cd "$(dirname "$0")"

DOCKER="$(command -v docker || command -v podman)"
if [[ -x .venv/bin/python ]]; then
  PYTHON="$(pwd)/.venv/bin/python"
else
  PYTHON="$(command -v python3 || command -v python)"
fi
AGENTGW="$(command -v agentgateway)"
KEEP_KC=false
[[ "${1:-}" == "--keep" ]] && KEEP_KC=true

GREEN='\033[0;32m'; RED='\033[0;31m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'
banner() { echo -e "\n${CYAN}▶ $*${NC}"; }
info()   { echo -e "${GREEN}  ✓${NC} $*"; }
fail()   { echo -e "${RED}  ✗ FAIL${NC}: $*"; FAILURES=$((FAILURES+1)); }
pass()   { echo -e "${GREEN}  ✓ PASS${NC}: $*"; PASSES=$((PASSES+1)); }
wait_for_port() {
  local host=$1
  local port=$2
  for _ in $(seq 1 30); do
    nc -z "$host" "$port" >/dev/null 2>&1 && return 0
    sleep 1
  done
  return 1
}
run_agent() {
  local output=""
  local exit_code=1
  for _ in $(seq 1 10); do
    set +e
    output=$("$PYTHON" agent_demo.py "$@" 2>&1)
    exit_code=$?
    set -e
    [[ "$exit_code" -eq 0 ]] && { printf '%s' "$output"; return 0; }
    sleep 1
  done
  printf '%s' "$output"
  return "$exit_code"
}
PASSES=0; FAILURES=0
GW_PID=""; MCP_PID=""

# ─── Cleanup ──────────────────────────────────────────────────────────────────
cleanup() {
  echo -e "\n${YELLOW}Tearing down...${NC}"
  [[ -n "$GW_PID"  ]] && kill "$GW_PID"  2>/dev/null || true
  [[ -n "$MCP_PID" ]] && kill "$MCP_PID" 2>/dev/null || true
  $DOCKER stop keycloak 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 1 — Infrastructure
# ═════════════════════════════════════════════════════════════════════════════
banner "Phase 1 — Start Infrastructure"

# Keycloak
if $KEEP_KC; then
  $DOCKER ps -q --filter name=keycloak | grep -q . || $DOCKER start keycloak > /dev/null
  info "Keycloak: reused"
else
  $DOCKER rm -f keycloak 2>/dev/null || true
  $DOCKER run -d --name keycloak \
    -p 8080:8080 -p 8081:9000 \
    -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=admin \
    -e KC_HEALTH_ENABLED="true" \
    quay.io/keycloak/keycloak:latest start-dev > /dev/null
  info "Keycloak: started"
fi

# Keycloak setup
bash setup_keycloak.sh > /dev/null
source .demo-secrets
info "Keycloak: realm + clients configured"

# MCP server
pkill -f "server.py" 2>/dev/null || true
pkill -f agentgateway 2>/dev/null || true
sleep 1
$PYTHON server.py > mcp_server.log 2>&1 &
MCP_PID=$!
sleep 2
kill -0 "$MCP_PID" 2>/dev/null || { echo "ERROR: MCP server failed to start"; exit 1; }
wait_for_port 127.0.0.1 9000 || { echo "ERROR: MCP server is not ready"; cat mcp_server.log; exit 1; }
info "MCP server: port 9000"

# AgentGateway
$AGENTGW -f config.yaml > agentgateway.log 2>&1 &
GW_PID=$!
sleep 3
kill -0 "$GW_PID" 2>/dev/null || { echo "ERROR: AgentGateway failed to start"; cat agentgateway.log; exit 1; }
wait_for_port ::1 15021 || { echo "ERROR: AgentGateway is not ready"; cat agentgateway.log; exit 1; }
info "AgentGateway: port 3000"

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 2 — Scenario A: mcp_reader — should be BLOCKED on delete
# ═════════════════════════════════════════════════════════════════════════════
banner "Phase 2 — Scenario A: mcp_reader agent"
echo "  client_id=$READER_CLIENT_ID"

set +e
READER_OUT=$(run_agent \
  --client-id "$READER_CLIENT_ID" \
  --client-secret "$READER_SECRET")
READER_EXIT=$?
set -e

echo "$READER_OUT"
echo ""

[[ "$READER_EXIT" -eq 0 ]] || fail "reader agent failed to complete"

# Assertions
if echo "$READER_OUT" | grep -q "mcp_reader"; then
  pass "Token contains mcp_reader role"
else
  fail "Token missing mcp_reader role"
fi

if echo "$READER_OUT" | grep -q "SUCCESS.*Customer cust_8819"; then
  pass "get_customer_summary returned data"
else
  fail "get_customer_summary did not succeed"
fi

if echo "$READER_OUT" | grep -q "BLOCKED BY GATEWAY"; then
  pass "delete_customer_account was BLOCKED"
else
  fail "delete_customer_account was NOT blocked — authorization rule may be broken"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 3 — Scenario B: mcp_admin — delete should SUCCEED
# ═════════════════════════════════════════════════════════════════════════════
banner "Phase 3 — Scenario B: mcp_admin agent"
echo "  client_id=$ADMIN_CLIENT_ID"

set +e
ADMIN_OUT=$(run_agent \
  --client-id "$ADMIN_CLIENT_ID" \
  --client-secret "$ADMIN_SECRET")
ADMIN_EXIT=$?
set -e

echo "$ADMIN_OUT"
echo ""

[[ "$ADMIN_EXIT" -eq 0 ]] || fail "admin agent failed to complete"

if echo "$ADMIN_OUT" | grep -q "mcp_admin"; then
  pass "Token contains mcp_admin role"
else
  fail "Token missing mcp_admin role"
fi

if echo "$ADMIN_OUT" | grep -q "ALLOWED.*purged\|SUCCESS.*purged"; then
  pass "delete_customer_account was ALLOWED for admin"
else
  fail "delete_customer_account was not allowed for admin"
fi

if echo "$ADMIN_OUT" | grep -q "BLOCKED"; then
  fail "Admin was unexpectedly BLOCKED"
fi

# ═════════════════════════════════════════════════════════════════════════════
# PHASE 4 — Scenario C: no token — should get 401
# ═════════════════════════════════════════════════════════════════════════════
banner "Phase 4 — Scenario C: invalid credentials"

UNAUTH_OUT=$($PYTHON agent_demo.py \
  --client-id "fake-client" \
  --client-secret "not-a-real-secret" 2>&1 || true)

echo "$UNAUTH_OUT" | head -5
echo ""

if echo "$UNAUTH_OUT" | grep -qiE "401|Unauthorized|rejected"; then
  pass "Invalid credentials rejected (401)"
else
  fail "Invalid credentials were NOT rejected — check Keycloak auth"
fi

# ═════════════════════════════════════════════════════════════════════════════
# Report
# ═════════════════════════════════════════════════════════════════════════════
TOTAL=$((PASSES + FAILURES))
echo ""
echo "══════════════════════════════════════"
if [[ $FAILURES -eq 0 ]]; then
  echo -e "${GREEN}  E2E RESULT: ALL $TOTAL CHECKS PASSED ✓${NC}"
else
  echo -e "${RED}  E2E RESULT: $FAILURES / $TOTAL CHECKS FAILED ✗${NC}"
fi
echo "══════════════════════════════════════"
echo ""

exit $FAILURES
