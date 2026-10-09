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

import hmac
import ipaddress
import logging
import os
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import JSONResponse

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
    with_storage: bool = False,
    *,
    local: bool = False,
) -> FastMCP:
    """
    Create a configured FastMCP server with all tools registered.
    
    Args:
        name: Server name
        with_storage: Whether to enable file upload storage (for remote deployments)
        local: The stdio server on the user's own machine. Only then are
            sessions unconfined (the paths are the user's own) and the admin
            tool registered. Anything else is treated as shared.
    
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
            "3. inspect_data, add_column and filter_dataframe read a small expression language, not arbitrary "
            "pandas code: column names, constants, arithmetic, comparisons, a few functions (np.log, np.where, "
            "pd.to_numeric...) and column summaries (mean, median, sum, nunique, unique, value_counts, describe). "
            "No groupby, apply or '@' references: use groupby_aggregate for aggregations. "
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
        max_sessions=MAX_SESSIONS,
        confine_files=not local,
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
    register_all_tools(mcp, session_manager, storage=storage, include_admin=local)

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
    mcp = create_mcp_server(with_storage=False, local=True)
    mcp.run()


MIN_AUTH_TOKEN_LENGTH = 16

# Not behind the bearer token: their encrypted, expiring link is their credential,
# and a browser following an upload link cannot send an Authorization header.
_TOKEN_EXEMPT_PATHS = ("/upload", "/api/upload")
_TOKEN_EXEMPT_PREFIXES = ("/download/",)


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def check_bind(host: str, auth_token: str | None, allow_no_auth: bool) -> None:
    """Refuse to serve beyond this machine without a bearer token.

    ``serve`` used to bind 0.0.0.0 with no authentication, so anyone who could
    reach the port could use every tool (security scan, 8 Oct 2026, F3).
    """
    if auth_token is not None and len(auth_token) < MIN_AUTH_TOKEN_LENGTH:
        raise SystemExit(
            f"The auth token must be at least {MIN_AUTH_TOKEN_LENGTH} characters."
        )
    if _is_loopback(host) or auth_token:
        return
    if allow_no_auth:
        logger.warning(
            "Serving on %s without authentication: anyone who can reach this port "
            "can use every tool. Only do this on a network you trust.", host
        )
        return
    raise SystemExit(
        f"Refusing to serve on {host} without authentication. Set "
        "STATS_COMPASS_AUTH_TOKEN (or --auth-token), bind to 127.0.0.1, or pass "
        "--no-auth on a network you trust."
    )


_LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "[::1]"}


def _host_name(value: str) -> str:
    """The host part of a Host header or an origin, without scheme or port."""
    value = value.split("://", 1)[-1].split("/", 1)[0]
    if value.startswith("["):
        return value.split("]", 1)[0] + "]"
    return value.rsplit(":", 1)[0] if value.count(":") == 1 else value


class LoopbackOnlyMiddleware:
    """403 unless Host, and Origin when sent, name this machine.

    Without a token, loopback serve trusts whoever reaches it, and a web page
    whose name has been rebound to 127.0.0.1 reaches it as same-origin: it could
    open sessions until the user's was evicted (re-scan of 0.3.32, F4). A
    rebound page still sends its own name as Host and Origin.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            host = _host_name(headers.get(b"host", b"").decode("latin-1"))
            origin = headers.get(b"origin")
            origin_ok = origin is None or _host_name(origin.decode("latin-1")) in _LOOPBACK_HOSTS
            if host not in _LOOPBACK_HOSTS or not origin_ok:
                response = JSONResponse({"error": "forbidden host or origin"}, status_code=403)
                await response(scope, receive, send)
                return
        await self.app(scope, receive, send)


class BearerAuthMiddleware:
    """401 for any HTTP request without ``Authorization: Bearer <token>``,
    except the upload and download routes."""

    def __init__(self, app, token: str):
        self.app = app
        self._expected = f"Bearer {token}".encode()

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope.get("path", "")
            exempt = path in _TOKEN_EXEMPT_PATHS or path.startswith(_TOKEN_EXEMPT_PREFIXES)
            if not exempt:
                supplied = dict(scope.get("headers", [])).get(b"authorization", b"")
                if not hmac.compare_digest(supplied, self._expected):
                    response = JSONResponse(
                        {"error": "unauthorized"},
                        status_code=401,
                        headers={"WWW-Authenticate": "Bearer"},
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


def create_http_app(auth_token: str | None = None, host: str = "127.0.0.1"):
    """The HTTP app: MCP plus upload and download routes, behind the token if given.

    Without a token on a loopback address, only requests naming this machine in
    Host and Origin get through (DNS rebinding). With a token, or a public bind
    with --no-auth, the Host is whatever the operator's name is.
    """
    from starlette.applications import Starlette
    from starlette.routing import Mount

    from stats_compass_mcp.image_utils import _inline_images_ctx, set_inline_images
    from stats_compass_mcp.upload import create_upload_routes

    set_inline_images(False)  # Default: strip images in HTTP mode

    mcp = create_mcp_server(with_storage=True)

    # Create combined app with MCP + upload routes
    mcp_app = mcp.http_app()
    upload_routes = create_upload_routes()

    # Middleware: opt individual requests into inline images via X-Inline-Images: 1 header
    class InlineImagesMiddleware:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] == "http":
                headers = dict(scope.get("headers", []))
                if headers.get(b"x-inline-images") == b"1":
                    token = _inline_images_ctx.set(True)
                    try:
                        await self.app(scope, receive, send)
                    finally:
                        _inline_images_ctx.reset(token)
                    return
            await self.app(scope, receive, send)

    # Combine routes: upload routes first, then mount MCP app
    # IMPORTANT: Pass mcp_app.lifespan to initialize the task group
    app = InlineImagesMiddleware(Starlette(
        routes=[
            *upload_routes,
            Mount("/", mcp_app),  # MCP handles /mcp and /sse
        ],
        lifespan=mcp_app.lifespan,  # Required for FastMCP's async task group
    ))
    if auth_token:
        app = BearerAuthMiddleware(app, auth_token)
    elif _is_loopback(host):
        app = LoopbackOnlyMiddleware(app)
    return app


def run_http(
    host: str = "127.0.0.1",
    port: int = 8000,
    auth_token: str | None = None,
    allow_no_auth: bool = False,
) -> None:
    """Run server with HTTP transport (for remote deployments).

    Binds 127.0.0.1 unless told otherwise; any other address needs a bearer
    token (``auth_token`` or STATS_COMPASS_AUTH_TOKEN) or ``allow_no_auth``.
    """
    import uvicorn

    auth_token = auth_token or os.getenv("STATS_COMPASS_AUTH_TOKEN") or None
    check_bind(host, auth_token, allow_no_auth)

    logger.info(f"Starting Stats Compass MCP (HTTP transport) at {host}:{port}")
    logger.info(f"Config: memory_limit={MEMORY_LIMIT_MB}MB, max_sessions={MAX_SESSIONS}")
    logger.info("Authentication: %s", "bearer token" if auth_token else "none (local only)")
    from stats_compass_mcp.tokens import KEY_SOURCE

    if KEY_SOURCE == "generated":
        logger.warning(
            "STATS_COMPASS_SECRET_KEY is unset: upload and download links are encrypted "
            "with a key generated for this process and stop working on restart."
        )
    else:
        logger.info("Upload and download links are encrypted with STATS_COMPASS_SECRET_KEY.")
    logger.info("Upload endpoints: GET /upload, POST /api/upload")

    # Session folders are named by HMAC here: the session id is the session's
    # credential in serve mode, and folder paths reach logs and listings.
    from stats_compass_mcp.safety import set_session_folder_namer
    from stats_compass_mcp.tokens import folder_name

    set_session_folder_namer(folder_name)

    uvicorn.run(
        create_http_app(auth_token, host=host),
        host=host,
        port=port,
    )


# Allow running directly for testing
if __name__ == "__main__":
    run_stdio()
