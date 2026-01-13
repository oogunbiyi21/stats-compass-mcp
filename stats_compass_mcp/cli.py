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
    
    # serve command (local stdio server)
    serve_parser = subparsers.add_parser("serve", help="Start the local MCP server (stdio)")
    
    # serve-remote command (FastMCP HTTP server)
    remote_parser = subparsers.add_parser("serve-remote", help="Start the remote HTTP server")
    remote_parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host to bind to (default: 0.0.0.0)",
    )
    remote_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )
    
    # bridge command (stdio-to-HTTP proxy for Claude Desktop)
    bridge_parser = subparsers.add_parser(
        "bridge",
        help="Start stdio-to-HTTP bridge (for Claude Desktop remote connections)"
    )
    bridge_parser.add_argument(
        "url",
        nargs="?",
        default="http://localhost:8000/mcp",
        help="Remote server URL (default: http://localhost:8000/mcp)",
    )
    
    # list-tools command
    subparsers.add_parser("list-tools", help="List all available tools")

    # install-local command (local server)
    install_parser = subparsers.add_parser("install-local", help="Install local server for Claude Desktop/VS Code")
    
    # install-remote command (bridge to remote server)
    install_remote_parser = subparsers.add_parser("install-remote", help="Install remote server bridge for Claude Desktop/VS Code")
    install_remote_parser.add_argument(
        "--url",
        default="http://localhost:8000/mcp",
        help="Remote server URL (default: http://localhost:8000/mcp)",
    )
    install_remote_parser.add_argument(
        "--dev",
        action="store_true",
        help="Use local Python instead of uvx (for development)",
    )
    
    args = parser.parse_args()
    
    if args.command == "serve":
        from stats_compass_mcp.local.server import run_server
        run_server()
    elif args.command == "serve-remote":
        import uvicorn
        from stats_compass_mcp.remote.server import mcp
        uvicorn.run(
            mcp.http_app(),
            host=args.host,
            port=args.port,
            log_level="info"
        )
    elif args.command == "bridge":
        from stats_compass_mcp.remote.bridge import run_bridge
        run_bridge(args.url)
    elif args.command == "list-tools":
        from stats_compass_mcp.local.tools import get_all_tools
        from stats_compass_core.registry import registry
        registry.auto_discover()
        tools = get_all_tools()
        print(f"Found {len(tools)} tools:\n")
        for tool in tools:
            print(f"  {tool['name']}: {tool['description'][:60]}...")
    elif args.command == "install-local":
        from stats_compass_mcp.local.install import main as install_main
        install_main()
    elif args.command == "install-remote":
        from stats_compass_mcp.remote.install import main as install_remote_main
        install_remote_main(server_url=args.url, use_uvx=not args.dev)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
