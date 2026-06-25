#!/usr/bin/env bash
# =============================================================================
# setup_keycloak.sh - Auto-configure Keycloak for the MCP security demo
# Replaces all 7 manual UI steps from the presentation guide.
# =============================================================================
set -euo pipefail

KEYCLOAK_URL="http://localhost:8080"
KEYCLOAK_HEALTH_URL="http://localhost:8081/health/ready"
ADMIN_USER="admin"
ADMIN_PASS="admin"
REALM="ai-mesh"

# Color helpers
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
info()    { echo -e "${GREEN}[setup]${NC} $*" >&2; }
warning() { echo -e "${YELLOW}[warn]${NC}  $*" >&2; }

# ─── 1. Wait for Keycloak to be ready ─────────────────────────────────────────
info "Waiting for Keycloak at $KEYCLOAK_HEALTH_URL ..."
for i in $(seq 1 40); do
  if curl -sf "$KEYCLOAK_HEALTH_URL" > /dev/null 2>&1; then
    info "Keycloak is ready."
    break
  fi
  echo -n "."
  sleep 3
  if [[ $i -eq 40 ]]; then
    echo -e "\n${RED}ERROR: Keycloak did not start in time.${NC}"
    exit 1
  fi
done

# ─── 2. Get admin access token ────────────────────────────────────────────────
info "Obtaining admin token..."
ADMIN_TOKEN=$(curl -sf -X POST "$KEYCLOAK_URL/realms/master/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=admin-cli&username=$ADMIN_USER&password=$ADMIN_PASS&grant_type=password" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

AUTH="Authorization: Bearer $ADMIN_TOKEN"

# ─── 3. Create realm ai-mesh ──────────────────────────────────────────────────
info "Creating realm '$REALM'..."
REALM_EXISTS=$(curl -sf -H "$AUTH" "$KEYCLOAK_URL/admin/realms/$REALM" > /dev/null 2>&1 && echo yes || echo no)
if [[ "$REALM_EXISTS" == "yes" ]]; then
  warning "Realm '$REALM' already exists - skipping creation."
else
  curl -sf -X POST "$KEYCLOAK_URL/admin/realms" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"realm\":\"$REALM\",\"enabled\":true}" > /dev/null
  info "Realm '$REALM' created."
fi

# ─── 4. Create realm roles ────────────────────────────────────────────────────
create_role() {
  local role=$1
  info "Creating realm role '$role'..."
  curl -sf -X POST "$KEYCLOAK_URL/admin/realms/$REALM/roles" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"name\":\"$role\"}" > /dev/null 2>&1 || warning "Role '$role' may already exist."
}
create_role "mcp_reader"
create_role "mcp_admin"

# ─── 5. Helper: create a service-account client and return its secret ─────────
create_client() {
  local client_id=$1
  local role=$2

  info "Creating client '$client_id'..."
  curl -sf -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "{
      \"clientId\": \"$client_id\",
      \"enabled\": true,
      \"clientAuthenticatorType\": \"client-secret\",
      \"standardFlowEnabled\": false,
      \"directAccessGrantsEnabled\": false,
      \"serviceAccountsEnabled\": true,
      \"publicClient\": false
    }" > /dev/null 2>&1 || warning "Client '$client_id' may already exist."

  # Get internal UUID
  local uuid
  uuid=$(curl -sf -H "$AUTH" "$KEYCLOAK_URL/admin/realms/$REALM/clients?clientId=$client_id" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d[0]['id'])")

  # Add Audience mapper so 'account' appears in JWT aud claim
  info "  Adding audience mapper to '$client_id'..."
  curl -sf -X POST "$KEYCLOAK_URL/admin/realms/$REALM/clients/$uuid/protocol-mappers/models" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "{
      \"name\": \"audience-account\",
      \"protocol\": \"openid-connect\",
      \"protocolMapper\": \"oidc-audience-mapper\",
      \"config\": {
        \"included.client.audience\": \"account\",
        \"id.token.claim\": \"false\",
        \"access.token.claim\": \"true\"
      }
    }" > /dev/null 2>&1 || warning "  Audience mapper may already exist."

  # Assign role to the service account
  local svc_user_id
  svc_user_id=$(curl -sf -H "$AUTH" \
    "$KEYCLOAK_URL/admin/realms/$REALM/clients/$uuid/service-account-user" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  local role_id
  role_id=$(curl -sf -H "$AUTH" \
    "$KEYCLOAK_URL/admin/realms/$REALM/roles/$role" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

  info "  Assigning role '$role' to '$client_id'..."
  curl -sf -X POST "$KEYCLOAK_URL/admin/realms/$REALM/users/$svc_user_id/role-mappings/realm" \
    -H "$AUTH" -H "Content-Type: application/json" \
    -d "[{\"id\":\"$role_id\",\"name\":\"$role\"}]" > /dev/null 2>&1 || warning "  Role already assigned."

  # Return the client secret
  local secret
  secret=$(curl -sf -H "$AUTH" \
    "$KEYCLOAK_URL/admin/realms/$REALM/clients/$uuid/client-secret" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['value'])")
  echo "$secret"
}

# ─── 6. Create both clients ───────────────────────────────────────────────────
READER_SECRET=$(create_client "agent-core-client" "mcp_reader")
ADMIN_SECRET=$(create_client "adminuser" "mcp_admin")

# ─── 7. Patch secrets into demo files ────────────────────────────────────────
DIR="$(dirname "$0")"

patch_secret() {
  local file=$1 secret=$2
  if [[ -f "$file" ]]; then
    # Use python3 for reliable in-place replacement (handles special chars in secret)
    python3 - "$file" "$secret" <<'PYEOF'
import sys, re, pathlib
f, secret = pathlib.Path(sys.argv[1]), sys.argv[2]
content = f.read_text()
content = re.sub(r'CLIENT_SECRET\s*=\s*"[^"]*"', f'CLIENT_SECRET = "{secret}"', content)
f.write_text(content)
PYEOF
  fi
}

info "Patching secrets into demo scripts..."
patch_secret "$DIR/agent_demo.py"       "$READER_SECRET"
patch_secret "$DIR/agent_demo_admin.py" "$ADMIN_SECRET"
info "  agent_demo.py       → agent-core-client (mcp_reader)"
info "  agent_demo_admin.py → adminuser (mcp_admin)"

# ─── 8. Write secrets file (for start.sh / e2e.sh to source) ─────────────────
cat > .demo-secrets <<SECRETS
READER_CLIENT_ID=agent-core-client
READER_SECRET=$READER_SECRET
ADMIN_CLIENT_ID=adminuser
ADMIN_SECRET=$ADMIN_SECRET
SECRETS
info "Secrets written to .demo-secrets"

# ─── 9. Print summary ────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════${NC}" >&2
echo -e "${GREEN}  Keycloak Setup Complete!${NC}" >&2
echo -e "${GREEN}════════════════════════════════════════════════════${NC}" >&2
echo ""
echo "  Realm:  $REALM   |   Roles: mcp_reader, mcp_admin"
echo ""
echo "  READER (gets BLOCKED on delete):"
echo "    --client-id agent-core-client --client-secret $READER_SECRET"
echo ""
echo "  ADMIN (delete ALLOWED):"
echo "    --client-id adminuser --client-secret $ADMIN_SECRET"
echo ""
