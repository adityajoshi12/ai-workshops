"""
agent_demo.py — MCP Security Demo Agent

Usage:
    python3 agent_demo.py                                        # uses env vars or defaults
    python3 agent_demo.py --client-id <id> --client-secret <s>  # explicit credentials

Environment variables (alternative to flags):
    CLIENT_ID      Keycloak client ID    (default: agent-core-client)
    CLIENT_SECRET  Keycloak client secret
"""
import asyncio
import argparse
import os
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

KEYCLOAK_TOKEN_URL = "http://localhost:8080/realms/ai-mesh/protocol/openid-connect/token"
GATEWAY_MCP_URL    = "http://localhost:3000/mcp"

# ── CLI / env-var config ──────────────────────────────────────────────────────
def parse_args():
    parser = argparse.ArgumentParser(description="MCP security demo agent")
    parser.add_argument("--client-id",     default=os.getenv("CLIENT_ID",     "agent-core-client"))
    parser.add_argument("--client-secret", default=os.getenv("CLIENT_SECRET", ""))
    return parser.parse_args()

# ── Auth ──────────────────────────────────────────────────────────────────────
async def get_token(client_id: str, client_secret: str) -> str:
    print(f"🔑 Fetching OAuth2 Token  (client_id={client_id})")
    async with httpx.AsyncClient() as client:
        resp = await client.post(KEYCLOAK_TOKEN_URL, data={
            "client_id":     client_id,
            "client_secret": client_secret,
            "grant_type":    "client_credentials",
        })
        resp.raise_for_status()
        token = resp.json()["access_token"]
        import base64, json as _json
        payload = token.split(".")[1]
        payload += "=" * (4 - len(payload) % 4)
        claims = _json.loads(base64.b64decode(payload))
        roles = [r for r in claims.get("realm_access", {}).get("roles", [])
                 if not r.startswith("default-") and r not in ("offline_access", "uma_authorization")]
        print(f"   ✅ Token issued. Effective roles: {roles}")
        return token

# ── MCP session helper ────────────────────────────────────────────────────────
async def call_tool(headers: dict, tool: str, args: dict):
    """Each call gets its own session — prevents ExceptionGroup leakage on denied calls."""
    async with streamablehttp_client(GATEWAY_MCP_URL, headers=headers) as (rs, ws, _):
        async with ClientSession(rs, ws) as session:
            await session.initialize()
            return await session.call_tool(tool, arguments=args)

# ── Demo ──────────────────────────────────────────────────────────────────────
async def main():
    args = parse_args()
    if not args.client_secret:
        print("ERROR: --client-secret is required  (or set CLIENT_SECRET env var)")
        raise SystemExit(1)

    try:
        token = await get_token(args.client_id, args.client_secret)
    except httpx.HTTPStatusError as e:
        print(f"ERROR: Token request rejected — HTTP {e.response.status_code} Unauthorized")
        print("       Check client_id / client_secret and that Keycloak is running.")
        raise SystemExit(1)

    headers = {"Authorization": f"Bearer {token}"}

    print("\n🔌 Connecting to AgentGateway → MCP Server")
    print("=" * 52 + "\n")

    # ── TEST 1: Safe read operation ───────────────────────────────────────────
    print("🛠️  AGENT ACTION: get_customer_summary('cust_8819')")
    try:
        result = await call_tool(headers, "get_customer_summary", {"customer_id": "cust_8819"})
        print(f"🟢 SUCCESS: {result.content[0].text}\n")
    except Exception as e:
        print(f"🔴 ERROR: {e}\n")

    # ── TEST 2: Destructive operation — the mic-drop moment ───────────────────
    print("💣 AGENT ACTION: delete_customer_account('cust_8819')")
    try:
        result = await call_tool(headers, "delete_customer_account", {"customer_id": "cust_8819"})
        print(f"🟢 ALLOWED: {result.content[0].text}\n")
    except Exception:
        print("🛡️  BLOCKED BY GATEWAY: delete_customer_account")
        print("   (Reason: token lacks 'mcp_admin' role — gateway hides the tool entirely)\n")

if __name__ == "__main__":
    import logging
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("mcp").setLevel(logging.CRITICAL)   # silence SDK's ClosedResourceError noise
    asyncio.run(main())
