"""
Tool registration for Stats Compass MCP server.

This is the single entry point for registering all tools with a FastMCP server.
"""

from fastmcp import FastMCP

from stats_compass_mcp.session import SessionManager
from stats_compass_mcp.tools.data import register_data_tools
from stats_compass_mcp.tools.parent import register_parent_tools
from stats_compass_mcp.tools.workflows import register_workflow_tools


def register_all_tools(
    mcp: FastMCP,
    session_manager: SessionManager,
    storage=None
) -> None:
    """
    Register all Stats Compass tools with the FastMCP server.
    
    This is the single source of truth for tool registration.
    Both stdio and HTTP transports use this same function.
    
    Args:
        mcp: FastMCP server instance
        session_manager: SessionManager for session isolation
        storage: Optional storage backend for file uploads (remote only)
    """
    # Data management tools (includes remote-only upload tools if storage provided)
    register_data_tools(mcp, session_manager, storage=storage)

    # Parent describe/execute tools
    register_parent_tools(mcp, session_manager)

    # Workflow tools
    register_workflow_tools(mcp, session_manager)
