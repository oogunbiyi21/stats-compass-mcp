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

__version__ = "0.3.21"

from stats_compass_mcp.server import create_mcp_server, run_http, run_stdio
from stats_compass_mcp.session import Session, SessionManager, get_session
from stats_compass_mcp.exports import set_download_url_builder

__all__ = [
    "create_mcp_server",
    "run_stdio",
    "run_http",
    "Session",
    "SessionManager",
    "get_session",
    "set_download_url_builder",
]
