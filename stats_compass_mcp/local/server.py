"""
MCP Server for stats-compass-core (Local/stdio transport).

Exposes all tools via the Model Context Protocol using stdio transport.
"""

import json
import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Prompt,
    PromptMessage,
    GetPromptResult,
)
from pydantic import BaseModel

from stats_compass_core.state import DataFrameState
from stats_compass_core.registry import registry
from stats_compass_core.results import ChartResult, ClassificationCurveResult
from stats_compass_core.workflows.results import WorkflowResult
from stats_compass_core.parent.schemas import ExecuteResult

from stats_compass_mcp.local.tools import get_all_tools
from stats_compass_mcp.workflow_summary import summarize_workflow_result

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

    # Write out the current tool schemas for easier client-debugging
    try:
        debug_dump = [
            {"name": t["name"], "input_schema": t.get("input_schema", {})}
            for t in tools
        ]
        with open("/tmp/stats_compass_mcp_tools_debug.json", "w", encoding="utf-8") as f:
            json.dump(debug_dump, f, indent=2)
        logger.info("Wrote tool schemas to /tmp/stats_compass_mcp_tools_debug.json")
    except Exception as exc:  # pragma: no cover - only used for local debugging
        logger.debug(f"Could not write debug tool schema dump: {exc}")
    
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
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | ImageContent | EmbeddedResource]:
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
            
            # Handle ChartResult specifically - image first, then metadata
            if isinstance(result, ChartResult) or isinstance(result, ClassificationCurveResult):
                contents: list[TextContent | ImageContent | EmbeddedResource] = []
                
                # Image first if we have one
                if result.image_base64:
                    title = result.title if hasattr(result, "title") else result.curve_type
                    logger.info(f"Returning chart image: {title}, size={len(result.image_base64)} bytes")
                    contents.append(ImageContent(
                        type="image",
                        data=result.image_base64,
                        mimeType="image/png"
                    ))
                
                # Then text metadata (strip the base64 from the JSON)
                result_data = result.model_dump()
                if "image_base64" in result_data:
                    result_data["image_base64"] = "[IMAGE_RETURNED_ABOVE]" if result.image_base64 else None
                contents.append(TextContent(
                    type="text",
                    text=json.dumps(result_data, default=str, indent=2)
                ))
                return contents

            # Convert result to JSON-serializable format
            if isinstance(result, BaseModel):
                result_data = result.model_dump()
            elif hasattr(result, "to_dict"):
                result_data = result.to_dict()
            else:
                result_data = result
            
            # Handle WorkflowResult: summarize text, return charts as images FIRST
            if isinstance(result, WorkflowResult):
                # Extract chart images
                chart_images = []
                for chart in result.artifacts.charts:
                    if chart.base64_image:
                        chart_images.append(ImageContent(
                            type="image",
                            data=chart.base64_image,
                            mimeType="image/png"
                        ))
                
                # Create compact summary instead of full verbose output
                summary_data = summarize_workflow_result(result_data)
                logger.info(f"Workflow result: returning {len(chart_images)} charts + summary")
                
                # Return images FIRST, then text summary (so charts appear before JSON)
                contents: list[TextContent | ImageContent | EmbeddedResource] = []
                contents.extend(chart_images)
                contents.append(TextContent(
                    type="text",
                    text=json.dumps(summary_data, default=str, indent=2),
                ))
                return contents
            
            # Handle ExecuteResult from parent tools (execute_cleaning, execute_plots, etc.)
            # The nested result may contain image_base64 from chart tools
            if isinstance(result, ExecuteResult) and result.result:
                nested_result = result.result
                # Check if nested result has an image
                if isinstance(nested_result, dict) and nested_result.get("image_base64"):
                    contents: list[TextContent | ImageContent | EmbeddedResource] = []
                    
                    # Image FIRST
                    contents.append(ImageContent(
                        type="image",
                        data=nested_result["image_base64"],
                        mimeType="image/png"
                    ))
                    
                    # Strip base64 from text response
                    result_data_stripped = result_data.copy()
                    if result_data_stripped.get("result"):
                        result_data_stripped["result"] = {
                            k: ("[IMAGE_RETURNED_ABOVE]" if k == "image_base64" else v)
                            for k, v in result_data_stripped["result"].items()
                        }
                    
                    contents.append(TextContent(
                        type="text",
                        text=json.dumps(result_data_stripped, default=str, indent=2)
                    ))
                    return contents
            
            return [TextContent(
                type="text",
                text=json.dumps(result_data, default=str, indent=2),
            )]
            
        except Exception as e:
            logger.error(f"Tool error: {e}")
            
            # Create a user-friendly error message
            error_msg = str(e)
            if isinstance(e, FileNotFoundError):
                error_msg = f"File not found. Please ensure you are using an absolute path to a file on the local machine. Error: {e}"
            
            return [TextContent(
                type="text",
                text=f"Error executing tool '{name}': {error_msg} ({type(e).__name__})"
            )]
    
    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """List available prompts."""
        return [
            Prompt(
                name="data-analyst",
                description="Standard instructions for data analysis with Stats Compass",
                arguments=[],
            )
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict[str, str] | None = None) -> GetPromptResult:
        """Get a specific prompt."""
        if name != "data-analyst":
            raise ValueError(f"Prompt '{name}' not found")

        return GetPromptResult(
            description="Standard instructions for data analysis with Stats Compass",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="""You are a data analysis assistant powered by Stats Compass.

CRITICAL INSTRUCTIONS:
1.  **Prioritize Tools:** ALWAYS use the provided `stats-compass` tools for data loading, cleaning, analysis, and visualization. Do NOT write custom Python code or build React/HTML artifacts unless the tools are insufficient or the user explicitly asks for them.
2.  **File Access:** You CANNOT see files dragged into the chat. You MUST ask the user for the absolute file path on their local machine and use `load_csv` or `load_excel`.
3.  **Visualization:** Use the plotting tools (`histogram`, `scatter_plot`, etc.) to generate charts. These tools return images directly. Do NOT try to generate React components for charts unless explicitly asked.
4.  **State Management:** Remember that data is stored in the server's state. You don't need to reload data for every operation. Use `list_dataframes` to see what's available.
"""
                    )
                )
            ]
        )

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
