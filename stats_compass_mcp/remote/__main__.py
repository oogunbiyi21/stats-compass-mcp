"""Run the remote Stats Compass HTTP server."""
import argparse

if __name__ == "__main__":
    import uvicorn
    from stats_compass_mcp.remote.server import mcp
    
    parser = argparse.ArgumentParser(description="Run the remote MCP server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    args = parser.parse_args()
    
    # Run the FastMCP server with uvicorn
    uvicorn.run(
        mcp.http_app(),
        host=args.host,
        port=args.port,
        log_level="info"
    )
