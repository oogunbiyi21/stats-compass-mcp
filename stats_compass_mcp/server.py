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
from pathlib import Path

from fastmcp import FastMCP

from stats_compass_mcp.session import SessionManager
from stats_compass_mcp.tools import register_all_tools

_RESOURCES_DIR = Path(__file__).parent / "resources"

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
            "Use load_dataset() for sample data, or load_csv()/load_excel() for local files. "
            "Do not rely on code generation for analysis - use the provided stats compass tools. "
            "\n\nWORKFLOW RULES:\n"
            "1. ALWAYS call describe_*_tools (e.g. describe_eda_tools) before using a tool category "
            "for the first time. Do not guess parameter names. One describe call is cheaper than a failed tool call. "
            "2. HYPOTHESIS TESTS: t_test and z_test require two separate columns (column_a, column_b). "
            "They do not accept a group_column parameter. "
            "First use split_column_by_group to reshape grouped data into wide format, then run the test. "
            "3. inspect_data is for scalar expressions only. Do not use it for value_counts(), groupby(), "
            "or any expression that returns a Series or DataFrame — these will fail. "
            "Use bar_chart or describe(include='all') for distributions, groupby_aggregate for aggregations. "
            "4. If a CSV fails to load with a codec error, retry with encoding='latin-1'. "
            "5. After run_preprocessing_workflow, use the new DataFrame name returned in the result, not the original. "
            "6. FINDING FILES: NEVER use bash, shell commands, or code execution to find files — "
            "these run in a cloud sandbox with no access to the user's machine. "
            "Always call the list_files MCP tool directly (e.g. list_files(directory='~/Downloads')). "
            "list_files is a top-level tool — do NOT route it through execute_data_tool. "
            "If you are unsure of a workflow or receive a validation error, call get_usage_guide first. "
            "7. DOWNLOAD LINKS: When any tool result contains a download_url field, always present it to the user as a clickable link. "
            "8. AXIS LABELS: When calling plot tools, always set xlabel and ylabel to descriptive labels. "
            "If you know the units (e.g. from context or column names like 'price_usd'), include them in the label (e.g. 'Price (USD)'). "
            "Never leave axis labels as raw column names if a more descriptive label is available."
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

    # Register resources
    @mcp.resource("stats-compass://skills")
    def skills_guide() -> str:
        """Agent skills guide: correct workflows and tool usage patterns."""
        return (_RESOURCES_DIR / "skills.md").read_text()

    @mcp.tool(annotations={"readOnlyHint": True})
    def get_usage_guide() -> str:
        """
        Return the Stats Compass usage guide covering correct tool workflows,
        hypothesis test patterns, and common pitfalls.

        Call this if you are unsure how to structure a statistical test,
        which tool to use for a task, or have received a validation error.
        """
        return (_RESOURCES_DIR / "skills.md").read_text()

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


def run_http(host: str = "0.0.0.0", port: int = 8000) -> None:  # nosec B104
    """Run server with HTTP transport (for remote deployments)."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from stats_compass_mcp.upload import create_upload_routes

    logger.info(f"Starting Stats Compass MCP (HTTP transport) at {host}:{port}")
    logger.info(f"Config: memory_limit={MEMORY_LIMIT_MB}MB, max_sessions={MAX_SESSIONS}")

    from stats_compass_mcp.image_utils import set_inline_images
    set_inline_images(False)

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
