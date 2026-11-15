import os

import httpx
from fastmcp import FastMCP

from metrics import fetch_metrics

mcp = FastMCP("Git Pulse Adda MCP")


@mcp.tool
async def get_developer_metrics(username: str, token: str = "") -> dict:
    """Fetch live GitHub profile, top repositories, and language metrics for a resume dashboard.

    Prefer setting GITHUB_TOKEN on the server over passing `token`: tool arguments can end up
    in client logs and conversation history."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            return await fetch_metrics(username, client, token)
    except httpx.HTTPError as e:
        return {"error": f"GitHub request failed: {type(e).__name__}"}


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port)
