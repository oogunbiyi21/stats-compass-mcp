"""
Stats Compass MCP Tools

Shared tool definitions for both stdio and HTTP transports.
"""

from stats_compass_mcp.tools.data import register_data_tools
from stats_compass_mcp.tools.parent import register_parent_tools
from stats_compass_mcp.tools.register import register_all_tools
from stats_compass_mcp.tools.workflows import register_workflow_tools

__all__ = [
    "register_all_tools",
    "register_data_tools",
    "register_parent_tools",
    "register_workflow_tools",
]
