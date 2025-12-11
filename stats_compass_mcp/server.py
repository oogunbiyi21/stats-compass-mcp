"""
MCP Server for stats-compass-core.

Exposes all tools via the Model Context Protocol.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
)
from pydantic import BaseModel

from stats_compass_core.state import DataFrameState
from stats_compass_core.registry import registry

from .tools import get_all_tools

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_server() -> Server:
    """Create and configure the MCP server."""
    server = Server("stats-compass")
    
    # Server-side state - one DataFrameState per session
    state = DataFrameState()
    
    # Load all tools from stats-compass-core
    registry.auto_discover()
    tools = get_all_tools()
    
    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available tools."""
        mcp_tools = []
        for tool in tools:
            mcp_tool = Tool(
                name=tool["name"],
                description=tool["description"] or f"{tool['category']} tool: {tool['original_name']}",
                inputSchema=tool.get("input_schema", {"type": "object", "properties": {}}),
            )
            mcp_tools.append(mcp_tool)
        return mcp_tools
    
    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Execute a tool and return results."""
        logger.info(f"Tool called: {name} with args: {arguments}")
        
        # Find the tool
        tool_info = None
        for t in tools:
            if t["name"] == name:
                tool_info = t
                break
        
        if not tool_info:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Tool '{name}' not found"}),
            )]
        
        try:
            # Validate and parse input if schema exists
            if "input_model" in tool_info:
                params = tool_info["input_model"](**arguments)
            else:
                params = arguments
            
            # Call the tool with state injected
            result = tool_info["function"](state, params)
            
            # Convert result to JSON-serializable format
            if isinstance(result, BaseModel):
                result_data = result.model_dump()
            elif hasattr(result, "to_dict"):
                result_data = result.to_dict()
            else:
                result_data = result
            
            return [TextContent(
                type="text",
                text=json.dumps(result_data, default=str, indent=2),
            )]
            
        except Exception as e:
            logger.error(f"Tool error: {e}")
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "error_type": type(e).__name__,
                }),
            )]
    
    return server


def run_server(transport: str = "stdio", port: int = 8000) -> None:
    """Run the MCP server."""
    import asyncio
    
    server = create_server()
    
    if transport == "stdio":
        logger.info("Starting Stats Compass MCP server (stdio transport)...")
        asyncio.run(run_stdio(server))
    elif transport == "sse":
        logger.info(f"Starting Stats Compass MCP server (SSE on port {port})...")
        # SSE transport would go here - for now just stdio
        raise NotImplementedError("SSE transport not yet implemented")


async def run_stdio(server: Server) -> None:
    """Run the server with stdio transport."""
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
