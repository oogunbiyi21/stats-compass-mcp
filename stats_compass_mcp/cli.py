"""
CLI entrypoint for stats-compass-mcp.
"""

import argparse
import sys
import logging

# Setup debug logging to file
logging.basicConfig(
    filename='/tmp/stats_compass_mcp_debug.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        prog="stats-compass-mcp",
        description="MCP server for stats-compass-core data analysis tools",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # serve command
    serve_parser = subparsers.add_parser("serve", help="Start the MCP server")
    serve_parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport protocol (default: stdio)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for SSE transport (default: 8000)",
    )
    
    # list-tools command
    subparsers.add_parser("list-tools", help="List all available tools")
    
    args = parser.parse_args()
    
    if args.command == "serve":
        from .server import run_server
        run_server(transport=args.transport, port=args.port)
    elif args.command == "list-tools":
        from .tools import list_tools
        list_tools()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
