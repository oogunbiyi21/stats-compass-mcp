"""
Remote Stats Compass MCP server using FastMCP.

This provides HTTP/SSE transport for remote MCP clients with automatic session isolation.

Architecture:
- Sessions are created automatically using FastMCP's MCP session ID
- Util tools: Defined here (storage management, session info - stable)
- Workflow tools: Imported from remote/workflow_tools.py (will grow)
- Parent tools: Imported from remote/parent_tools.py (will grow)

NOTE: This is single-instance only (in-memory sessions).
For production with multiple workers, use Redis for session storage.
"""

import logging
import os
from typing import Optional

import pandas as pd
from fastmcp import FastMCP, Context

from stats_compass_core import data as core_data
from stats_compass_mcp.remote.session import SessionManager, get_session
from stats_compass_mcp.remote.storage import StorageBackend, create_storage_backend
from stats_compass_mcp.remote import register_workflow_tools, register_parent_tools


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
# Initialize server and dependencies
# ============================================================================

mcp = FastMCP(
    "stats-compass-remote",
    instructions=(
        "Stats Compass is a data analysis toolkit. "
        "Sessions are created automatically - no need to call create_session. "
        "Your data is isolated to your session. "
        "Upload files using get_upload_url() and register_uploaded_file(), "
        "or load sample datasets with load_dataset()."
    )
)

# Module-level instances (single-instance server)
session_manager = SessionManager(
    memory_limit_mb=MEMORY_LIMIT_MB,
    max_sessions=MAX_SESSIONS
)
storage = create_storage_backend()


# ============================================================================
# Util Tools (stable - storage management, session info)
# ============================================================================

@mcp.tool()
def ping() -> dict:
    """Health check - verify server is running."""
    return {
        "status": "ok",
        "server": "stats-compass-remote",
        "message": "Server is running. Sessions are created automatically."
    }


@mcp.tool()
def session_info(ctx: Context) -> dict:
    """
    Get information about your current session.
    
    Returns:
        Session info including session_id, created_at, dataframes, models.
    """
    session = get_session(ctx, session_manager)
    return session.get_info()


@mcp.tool()
def list_dataframes(ctx: Context) -> dict:
    """
    List all DataFrames in your session.
    
    Returns:
        List of DataFrames with name, shape, columns, and active status.
    """
    session = get_session(ctx, session_manager)
    
    dataframes = session.state.list_dataframes()
    active = session.state.get_active()
    active_name = active.name if active is not None else None
    
    return {
        "dataframes": [
            {
                "name": df.name,
                "shape": list(df.shape),
                "columns": list(df.columns),
                "is_active": df.name == active_name
            }
            for df in dataframes
        ],
        "active_dataframe": active_name,
        "count": len(dataframes)
    }


@mcp.tool()
def get_upload_url(
    ctx: Context,
    filename: str,
    content_type: str = "text/csv"
) -> dict:
    """
    Get a presigned URL for uploading a file.
    
    For S3 storage: Returns a presigned PUT URL.
    For local storage: Returns a file path.
    
    Args:
        filename: Desired filename (e.g., "my_data.csv")
        content_type: MIME type (default: text/csv)
    
    Returns:
        Upload info with url, method, headers, file_key.
    """
    session = get_session(ctx, session_manager)
    
    return storage.get_upload_url(
        session_id=session.session_id,
        filename=filename,
        content_type=content_type
    )


@mcp.tool()
def register_uploaded_file(
    ctx: Context,
    file_key: str,
    dataframe_name: Optional[str] = None,
    file_type: str = "csv"
) -> dict:
    """
    Register an uploaded file and load it as a DataFrame.
    
    After uploading to the URL from get_upload_url(), call this
    to load the file into your session.
    
    Args:
        file_key: The file_key returned from get_upload_url()
        dataframe_name: Name for the DataFrame (default: filename without extension)
        file_type: File type - "csv" or "excel"
    
    Returns:
        DataFrame info with name, shape, columns, dtypes.
    """
    session = get_session(ctx, session_manager)
    
    if not storage.file_exists(session.session_id, file_key):
        return {"error": f"File not found: {file_key}. Did you upload it?"}
    
    file_path = storage.get_file_path(session.session_id, file_key)
    
    # Determine DataFrame name
    if not dataframe_name:
        dataframe_name = file_key.rsplit(".", 1)[0]
    
    # Load file
    try:
        if file_type.lower() == "excel":
            df = pd.read_excel(file_path)
        else:
            df = pd.read_csv(file_path)
    except Exception as e:
        return {"error": f"Failed to load file: {str(e)}"}
    
    # Register in session
    session.state.register(df, name=dataframe_name, set_active=True)
    
    return {
        "success": True,
        "dataframe_name": dataframe_name,
        "shape": list(df.shape),
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
    }


@mcp.tool()
def load_dataset(
    ctx: Context,
    name: str,
    set_active: bool = True
) -> dict:
    """
    Load a built-in sample dataset.
    
    Available datasets: TATASTEEL, Housing, Bukayo_Saka_7322
    
    Args:
        name: Dataset name
        set_active: Whether to set as active DataFrame (default: True)
    
    Returns:
        DataFrame info with name, shape, columns.
    """
    session = get_session(ctx, session_manager)
    
    from stats_compass_core.data.load_dataset import LoadDatasetInput
    params = LoadDatasetInput(name=name, set_active=set_active)
    result = core_data.load_dataset(state=session.state, params=params)
    return result.model_dump()


@mcp.tool()
def delete_session(ctx: Context) -> dict:
    """
    Delete your current session and all its data.
    
    Returns:
        Deletion result.
    """
    session = get_session(ctx, session_manager)
    session_id = session.session_id
    
    files_deleted = storage.delete_session_files(session_id)
    session_deleted = session_manager.delete(session_id)
    
    return {
        "success": session_deleted,
        "files_deleted": files_deleted,
        "message": "Session deleted" if session_deleted else "Session not found"
    }


@mcp.tool()
def server_stats() -> dict:
    """
    Get server statistics (admin tool).
    
    Returns:
        Active sessions count, configuration, and session details.
    """
    return session_manager.get_stats()


# ============================================================================
# Register workflow and parent tools
# ============================================================================

register_workflow_tools(mcp, session_manager)
register_parent_tools(mcp, session_manager)


# ============================================================================
# CLI entry point
# ============================================================================

def main():
    """Run the FastMCP server."""
    import uvicorn
    
    host = os.getenv("STATS_COMPASS_HOST", "0.0.0.0")
    port = int(os.getenv("STATS_COMPASS_PORT", "8000"))
    
    logger.info(f"Starting Stats Compass Remote at {host}:{port}")
    logger.info(f"Config: memory_limit={MEMORY_LIMIT_MB}MB, max_sessions={MAX_SESSIONS}")
    
    # Run with HTTP/SSE transport
    uvicorn.run(
        mcp.http_app(),
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
