"""
CLI entrypoint for stats-compass-mcp.

Commands:
    run          Start local MCP server (stdio transport)
    serve        Start HTTP server (for remote deployments)
    list-tools   List all available tools
    install      Install for Claude Desktop/VS Code
"""

import argparse
import logging
import sys

# Setup debug logging to file
logging.basicConfig(
    filename='/tmp/stats_compass_mcp_debug.log',  # nosec B108
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

    # run command (stdio transport - for local use)
    subparsers.add_parser(
        "run",
        help="Start local MCP server (stdio transport, for Claude Desktop/VS Code)"
    )

    # serve command (HTTP transport - for remote/Docker)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Start HTTP server (for remote deployments, Docker)"
    )
    serve_parser.add_argument(
        "--host",
        default="0.0.0.0",  # nosec B104 - intentional for Docker/server
        help="Host to bind to (default: 0.0.0.0)",
    )
    serve_parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind to (default: 8000)",
    )

    # list-tools command
    subparsers.add_parser("list-tools", help="List all available tools")

    # install command
    install_parser = subparsers.add_parser(
        "install",
        help="Install for Claude Desktop or VS Code"
    )
    install_parser.add_argument(
        "--client",
        choices=["claude", "vscode"],
        default="claude",
        help="Target MCP client (default: claude)",
    )
    install_parser.add_argument(
        "--remote-url",
        type=str,
        default=None,
        help="Also add remote server config (e.g., http://localhost:8000/mcp)",
    )

    args = parser.parse_args()

    if args.command == "run":
        from stats_compass_mcp.server import run_stdio
        run_stdio()

    elif args.command == "serve":
        from stats_compass_mcp.server import run_http
        run_http(host=args.host, port=args.port)

    elif args.command == "list-tools":
        # Create server and list its tools
        import asyncio

        from stats_compass_mcp.server import create_mcp_server

        mcp = create_mcp_server()

        # FastMCP stores tools in _tool_manager (async method)
        if hasattr(mcp, '_tool_manager'):
            tools = asyncio.run(mcp._tool_manager.get_tools())
            print(f"Found {len(tools)} tools:\n")
            for name, tool in tools.items():
                desc = tool.description[:60] + "..." if len(tool.description) > 60 else tool.description
                print(f"  {name}: {desc}")

    elif args.command == "install":
        _install_client(args.client, remote_url=args.remote_url)

    else:
        parser.print_help()
        sys.exit(1)


def _install_client(client: str, remote_url: str | None = None) -> None:
    """Install MCP server configuration for the specified client."""
    import json
    import platform
    from pathlib import Path

    if client == "claude":
        config_path = Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        servers_key = "mcpServers"
    else:  # vscode
        # VS Code config location varies by OS
        if platform.system() == "Darwin":  # macOS
            config_path = Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
        elif platform.system() == "Windows":
            config_path = Path.home() / "AppData" / "Roaming" / "Code" / "User" / "mcp.json"
        else:  # Linux
            config_path = Path.home() / ".config" / "Code" / "User" / "mcp.json"
        servers_key = "servers"

    # Ensure parent directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing config or create new
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}

    # Ensure servers key exists
    if servers_key not in config:
        config[servers_key] = {}

    # Add local stats-compass configuration
    config[servers_key]["stats-compass"] = {
        "command": "uvx",
        "args": ["stats-compass-mcp", "run"]
    }

    # Add remote config if URL provided
    if remote_url:
        if client == "vscode":
            # VS Code supports direct HTTP URLs
            config[servers_key]["stats-compass-remote"] = {
                "url": remote_url
            }
        else:  # claude
            # Claude Desktop needs mcp-proxy to bridge stdio to HTTP
            # FastMCP uses streamablehttp transport
            config[servers_key]["stats-compass-remote"] = {
                "command": "uvx",
                "args": ["mcp-proxy", "--transport", "streamablehttp", remote_url]
            }

    # Write config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"✅ Installed stats-compass for {client}")
    print(f"   Config: {config_path}")
    if remote_url:
        print(f"   Remote: {remote_url}")
        if client == "claude":
            print("   (using mcp-proxy for HTTP bridging)")
    print(f"\n   Restart {client.title()} to activate.")


if __name__ == "__main__":
    main()
