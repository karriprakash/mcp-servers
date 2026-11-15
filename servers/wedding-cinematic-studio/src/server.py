#!/usr/bin/env python3
"""Cinematic Wedding Studio: MCP server entrypoint.

Run (stdio):   python -m src.server
Claude Desktop config:
    {"mcpServers": {"wedding-studio": {
        "command": "python", "args": ["-m", "src.server"],
        "cwd": "/path/to/wedding_mcp",
        "env": {"GEMINI_API_KEY": "...", "WEDDING_STUDIO_HOME": "~/.wedding_studio"}}}}
"""
from __future__ import annotations

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
    mcp.run()


if __name__ == "__main__":
    main()
