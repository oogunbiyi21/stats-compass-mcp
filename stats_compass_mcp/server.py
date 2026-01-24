"""
Stats Compass MCP Server.

A unified MCP server that supports both stdio and HTTP transports.
All tool definitions are shared - only the transport differs.

Usage:
    # stdio (for Claude Desktop, VS Code local)
    stats-compass-mcp run
    
    # HTTP (for remote/hosted deployments)
    stats-compass-mcp serve --port 8000
"""

import logging
import os

from fastmcp import FastMCP

from stats_compass_mcp.session import SessionManager
from stats_compass_mcp.tools import register_all_tools

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# Configuration from environment
# ============================================================================

MEMORY_LIMIT_MB = float(os.getenv("STATS_COMPASS_MEMORY_LIMIT_MB", "500"))
MAX_SESSIONS = int(os.getenv("STATS_COMPASS_MAX_SESSIONS", "100"))


# ============================================================================
# Create server and dependencies
# ============================================================================

def create_mcp_server(
    name: str = "stats-compass",
    with_storage: bool = False
) -> FastMCP:
    """
    Create a configured FastMCP server with all tools registered.
    
    Args:
        name: Server name
        with_storage: Whether to enable file upload storage (for remote deployments)
    
    Returns:
        Configured FastMCP server
    """
    mcp = FastMCP(
        name,
        instructions=(
            "Stats Compass is a data analysis toolkit. "
            "Sessions are created automatically - no need to call create_session. "
            "Your data is isolated to your session. "
            "Use load_dataset() for sample data, or load_csv()/load_excel() for local files."
            "Do not rely on code generation for analysis - use the provided stats compass tools."
        )
    )

    # Create session manager (single instance)
    session_manager = SessionManager(
        memory_limit_mb=MEMORY_LIMIT_MB,
        max_sessions=MAX_SESSIONS
    )

    # Optional storage backend for remote deployments
    storage = None
    if with_storage:
        try:
            from stats_compass_mcp.storage import create_storage_backend
            storage = create_storage_backend()
            logger.info("Storage backend enabled for file uploads")
        except ImportError:
            logger.warning("Storage backend not available - file uploads disabled")

    # Register all tools (single source of truth)
    register_all_tools(mcp, session_manager, storage=storage)

    logger.info(f"Server '{name}' configured with {MAX_SESSIONS} max sessions")

    return mcp


# ============================================================================
# Module-level server instance (for CLI)
# ============================================================================

# This is created lazily when needed
_mcp: FastMCP | None = None


def get_server(with_storage: bool = False) -> FastMCP:
    """Get or create the MCP server instance."""
    global _mcp
    if _mcp is None:
        _mcp = create_mcp_server(with_storage=with_storage)
    return _mcp


# ============================================================================
# Entry points for different transports
# ============================================================================

def run_stdio() -> None:
    """Run server with stdio transport (for local MCP clients)."""
    logger.info("Starting Stats Compass MCP (stdio transport)")
    mcp = create_mcp_server(with_storage=False)
    mcp.run()


def run_http(host: str = "0.0.0.0", port: int = 8000) -> None:
    """Run server with HTTP transport (for remote deployments)."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from stats_compass_mcp.upload import create_upload_routes

    logger.info(f"Starting Stats Compass MCP (HTTP transport) at {host}:{port}")
    logger.info(f"Config: memory_limit={MEMORY_LIMIT_MB}MB, max_sessions={MAX_SESSIONS}")

    mcp = create_mcp_server(with_storage=True)

    # Create combined app with MCP + upload routes
    mcp_app = mcp.http_app()
    upload_routes = create_upload_routes()

    # Combine routes: upload routes first, then mount MCP app
    # IMPORTANT: Pass mcp_app.lifespan to initialize the task group
    app = Starlette(
        routes=[
            *upload_routes,
            Mount("/", mcp_app),  # MCP handles /mcp and /sse
        ],
        lifespan=mcp_app.lifespan,  # Required for FastMCP's async task group
    )

    logger.info("Upload endpoints: GET /upload, POST /api/upload")

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


# Allow running directly for testing
if __name__ == "__main__":
    run_stdio()
