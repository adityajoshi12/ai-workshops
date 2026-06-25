# server.py
from mcp.server.fastmcp import FastMCP

# 1. MOVE THE PORT (AND HOST) HERE TO THE CONSTRUCTOR
mcp = FastMCP("CustomerOps", host="0.0.0.0", port=9000, streamable_http_path="/mcp")

@mcp.tool()
def get_customer_summary(customer_id: str) -> str:
    """Safe operation: available to standard readers."""
    return f"Customer {customer_id}: Active status, standard tier."

@mcp.tool()
def delete_customer_account(customer_id: str) -> str:
    """Privileged operation: requires admin clearance."""
    return f"SUCCESS: Customer {customer_id} has been fully purged from the DB."

if __name__ == "__main__":
    mcp.run(transport='sse')
