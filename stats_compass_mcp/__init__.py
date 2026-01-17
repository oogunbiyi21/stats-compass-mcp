"""
stats-compass-mcp: MCP server for stats-compass-core tools.

Exposes data analysis tools to LLMs via the Model Context Protocol.
Supports both stdio (local) and HTTP (remote) transports.

Usage:
    # Local (stdio transport)
    stats-compass-mcp run
    
    # Remote (HTTP transport)
    stats-compass-mcp serve --port 8000
"""

__version__ = "0.2.0"

from stats_compass_mcp.server import create_mcp_server, run_stdio, run_http
from stats_compass_mcp.session import Session, SessionManager, get_session

__all__ = [
    "create_mcp_server",
    "run_stdio",
    "run_http",
    "Session",
    "SessionManager",
    "get_session",
]
