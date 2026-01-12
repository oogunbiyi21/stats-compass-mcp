#!/usr/bin/env python3
"""
Install script for Stats Compass local MCP server.

Configures Claude Desktop and VS Code to use the local stdio server.
"""

import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_config_path() -> Path:
    """Get the Claude Desktop config file path for the current platform."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.getenv("APPDATA")) / "Claude" / "claude_desktop_config.json"
    else:  # Linux
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_vscode_config_path() -> Path:
    """Get the VS Code MCP settings file path."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
    elif system == "Windows":
        return Path(os.getenv("APPDATA")) / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"
    else:  # Linux
        return Path.home() / ".config" / "Code" / "User" / "globalStorage" / "saoudrizwan.claude-dev" / "settings" / "cline_mcp_settings.json"


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent.parent


def install_claude_desktop() -> None:
    """Install configuration for Claude Desktop."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {"mcpServers": {}}
    
    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Get Python executable and project root
    python_path = sys.executable
    project_root = get_project_root()
    
    # Add stats-compass server
    config["mcpServers"]["stats-compass"] = {
        "command": python_path,
        "args": ["-m", "stats_compass_mcp.local.server"],
        "env": {
            "PYTHONPATH": str(project_root)
        }
    }
    
    # Write updated config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"✓ Installed stats-compass server in Claude Desktop config")
    print(f"  Config: {config_path}")
    print(f"  Python: {python_path}")
    print(f"  Project: {project_root}")
    print("\nRestart Claude Desktop to activate the server.")


def install_vscode() -> None:
    """Install configuration for VS Code."""
    config_path = get_vscode_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing config or create new
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {"mcpServers": {}}
    
    # Ensure mcpServers exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}
    
    # Get Python executable and project root
    python_path = sys.executable
    project_root = get_project_root()
    
    # Add stats-compass server
    config["mcpServers"]["stats-compass"] = {
        "command": python_path,
        "args": ["-m", "stats_compass_mcp.local.server"],
        "env": {
            "PYTHONPATH": str(project_root)
        }
    }
    
    # Write updated config
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    
    print(f"✓ Installed stats-compass server in VS Code config")
    print(f"  Config: {config_path}")
    print(f"  Python: {python_path}")
    print(f"  Project: {project_root}")
    print("\nRestart VS Code to activate the server.")


def main():
    """Main installation function."""
    print("Stats Compass Local MCP Server Installer")
    print("=" * 50)
    print()
    
    # Check if in virtual environment
    if not hasattr(sys, 'base_prefix') or sys.base_prefix == sys.prefix:
        print("⚠️  Warning: Not running in a virtual environment")
        print("   Consider using a venv or conda environment")
        print()
    
    # Ask which to install
    print("Install for:")
    print("  1. Claude Desktop")
    print("  2. VS Code (Cline/Claude Dev)")
    print("  3. Both")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    print()
    
    if choice == "1":
        install_claude_desktop()
    elif choice == "2":
        install_vscode()
    elif choice == "3":
        install_claude_desktop()
        print()
        install_vscode()
    else:
        print("Invalid choice")
        sys.exit(1)


if __name__ == "__main__":
    main()
