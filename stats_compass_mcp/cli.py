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

    # install command
    install_parser = subparsers.add_parser("install", help="Configure Claude Desktop automatically")
    install_parser.add_argument(
        "--dev",
        action="store_true",
        help="Configure for local development (uses current executable instead of uvx)",
    )

    # install-vscode command
    install_vscode_parser = subparsers.add_parser("install-vscode", help="Configure VS Code (GitHub Copilot) automatically")
    install_vscode_parser.add_argument(
        "--dev",
        action="store_true",
        help="Configure for local development (uses current executable instead of uvx)",
    )
    
    args = parser.parse_args()
    
    if args.command == "serve":
        from .server import run_server
        run_server(transport=args.transport, port=args.port)
    elif args.command == "list-tools":
        from .tools import list_tools
        list_tools()
    elif args.command == "install":
        from .install import install_claude_config
        install_claude_config(dev_mode=args.dev)
    elif args.command == "install-vscode":
        from .install import install_vscode_config
        install_vscode_config(dev_mode=args.dev)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
