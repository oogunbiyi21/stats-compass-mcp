import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Any

def get_claude_config_path() -> Path | None:
    """Get the path to the Claude Desktop config file based on OS."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    elif system == "Windows":
        return Path(os.environ["APPDATA"]) / "Claude" / "claude_desktop_config.json"
    else:
        return None

def get_vscode_config_path() -> Path | None:
    """Get the path to the VS Code MCP config file based on OS."""
    system = platform.system()
    
    if system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "mcp.json"
    elif system == "Windows":
        return Path(os.environ["APPDATA"]) / "Code" / "User" / "mcp.json"
    elif system == "Linux":
        return Path.home() / ".config" / "Code" / "User" / "mcp.json"
    else:
        return None

def install_claude_config(dev_mode: bool = False):
    """
    Configure Claude Desktop for Stats Compass.
    
    Args:
        dev_mode: If True, points to the current executable instead of using uvx.
    """
    print("🧭 Stats Compass - Claude Desktop Setup")
    print("=======================================")
    
    config_path = get_claude_config_path()
    if not config_path:
        print(f"❌ Unsupported operating system: {platform.system()}")
        return
        
    print(f"📂 Config file: {config_path}")
    
    # Ensure directory exists
    if not config_path.parent.exists():
        print(f"❌ Claude Desktop directory not found at {config_path.parent}")
        print("   Please install and run Claude Desktop first.")
        return
        
    # Read existing config or create new
    config: dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Backup existing config
            backup_path = config_path.with_suffix(".json.bak")
            shutil.copy2(config_path, backup_path)
            print(f"✅ Backed up existing config to {backup_path.name}")
            
        except json.JSONDecodeError:
            print("⚠️  Existing config file is invalid JSON. Creating new config.")
            # Backup invalid file just in case
            shutil.copy2(config_path, config_path.with_suffix(".json.corrupt"))
    
    # Prepare the stats-compass config
    if dev_mode:
        # Use the current python environment's executable
        # We assume stats-compass-mcp is in the same bin directory as python
        bin_dir = Path(sys.executable).parent
        executable = bin_dir / "stats-compass-mcp"
        
        print(f"🔧 Development mode: Using local executable at {executable}")
        
        mcp_config = {
            "command": str(executable),
            "args": ["serve"]
        }
    else:
        # Default production mode using uvx
        mcp_config = {
            "command": "uvx",
            "args": ["stats-compass-mcp", "serve"]
        }
    
    # Update config
    if "mcpServers" not in config:
        config["mcpServers"] = {}
        
    config["mcpServers"]["stats-compass"] = mcp_config
    
    # Write back
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print("✅ Successfully updated claude_desktop_config.json")
        print("\n🎉 Setup complete! Please restart Claude Desktop to see 'stats-compass' in your tools.")
        
    except Exception as e:
        print(f"❌ Failed to write config: {e}")

def install_vscode_config(dev_mode: bool = False):
    """
    Configure VS Code (GitHub Copilot) for Stats Compass.
    
    Args:
        dev_mode: If True, points to the current executable instead of using uvx.
    """
    print("🧭 Stats Compass - VS Code Setup")
    print("================================")
    
    config_path = get_vscode_config_path()
    if not config_path:
        print(f"❌ Unsupported operating system: {platform.system()}")
        return
        
    print(f"📂 Config file: {config_path}")
    
    # Ensure directory exists
    if not config_path.parent.exists():
        print(f"❌ VS Code User directory not found at {config_path.parent}")
        print("   Please install VS Code first.")
        return
        
    # Read existing config or create new
    config: dict[str, Any] = {}
    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
            
            # Backup existing config
            backup_path = config_path.with_suffix(".json.bak")
            shutil.copy2(config_path, backup_path)
            print(f"✅ Backed up existing config to {backup_path.name}")
            
        except json.JSONDecodeError:
            print("⚠️  Existing config file is invalid JSON. Creating new config.")
            # Backup invalid file just in case
            shutil.copy2(config_path, config_path.with_suffix(".json.corrupt"))
    
    # Prepare the stats-compass config
    if dev_mode:
        # Use the current python environment's executable
        bin_dir = Path(sys.executable).parent
        executable = bin_dir / "stats-compass-mcp"
        
        print(f"🔧 Development mode: Using local executable at {executable}")
        
        mcp_config = {
            "command": str(executable),
            "args": ["serve"]
        }
    else:
        # Default production mode using uvx
        mcp_config = {
            "command": "uvx",
            "args": ["stats-compass-mcp", "serve"]
        }
    
    # Update config (VS Code uses 'servers' not 'mcpServers')
    if "servers" not in config:
        config["servers"] = {}
        
    config["servers"]["stats-compass"] = mcp_config
    
    # Write back
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print("✅ Successfully updated mcp.json")
        print("\n🎉 Setup complete! Please reload VS Code to use 'stats-compass' with GitHub Copilot.")
        
    except Exception as e:
        print(f"❌ Failed to write config: {e}")
