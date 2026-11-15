#!/usr/bin/env python3
"""Cinematic Wedding Studio: MCP server entrypoint.

Run (stdio, default):  python -m src.server
Run over HTTP:         MCP_TRANSPORT=streamable-http MCP_HOST=127.0.0.1 MCP_PORT=8000 python -m src.server
                       (endpoint http://HOST:PORT/mcp). There is no authentication: keep it on
                       127.0.0.1 and reach it through an SSH tunnel, never expose it publicly.

Claude Desktop config (stdio):
    {"mcpServers": {"wedding-studio": {
        "command": "python", "args": ["-m", "src.server"],
        "cwd": "/path/to/servers/wedding-cinematic-studio",
        "env": {"GEMINI_API_KEY": "...", "WEDDING_STUDIO_HOME": "~/.wedding_studio"}}}}
"""
from __future__ import annotations

import os

try:  # mcp 2.x renamed FastMCP to MCPServer; keep working on both
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP

from . import config
from .tools import analysis, assembly, generation, storyboard, templates


def build_server() -> FastMCP:
    config.ensure_dirs()
    mcp = FastMCP("CinematicWeddingStudio")
    analysis.register(mcp)
    storyboard.register(mcp)
    templates.register(mcp)
    generation.register(mcp)
    assembly.register(mcp)
    return mcp


mcp = build_server()


def main() -> None:
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport != "stdio":
        try:  # mcp 1.x keeps host/port on settings
            mcp.settings.host = os.environ.get("MCP_HOST", "127.0.0.1")
            mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
        except AttributeError:
            pass
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
