"""
Tool loader and registry bridge for MCP.

Loads all tools from stats-compass-core and prepares them for MCP registration.
"""

from copy import deepcopy
from typing import Any

from stats_compass_core.registry import registry


def _normalize_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Make the JSON schema safer for strict tool validators.

    - Ensures every array schema has an `items` definition (some validators reject bare arrays).
    - Flattens simple `anyOf` optional shapes (e.g., string | null) into a single type so clients
      that don't fully support unions can still validate the schema.
    """
    def walk(node: Any) -> Any:
        if isinstance(node, dict):
            # Flatten `anyOf` that is just optional (type | null)
            if "anyOf" in node:
                non_null = [n for n in node["anyOf"] if n.get("type") != "null"]
                if len(non_null) == 1:
                    merged = {k: v for k, v in node.items() if k != "anyOf"}
                    merged.update(non_null[0])
                    node = merged

            # Add missing items for arrays
            if node.get("type") == "array" and not node.get("items"):
                node["items"] = {"type": "string"}

            for key, value in list(node.items()):
                node[key] = walk(value)
            return node
        if isinstance(node, list):
            return [walk(item) for item in node]
        return node

    return walk(deepcopy(schema))


def get_all_tools() -> list[dict[str, Any]]:
    """
    Get all registered tools from stats-compass-core.
    
    Returns:
        List of tool metadata dicts with name, category, description, and schema.
    """
    # Ensure tools are discovered
    registry.auto_discover()
    
    tools = []
    for metadata in registry.list_tools():
        tool_info: dict[str, Any] = {
            "name": f"{metadata.category}_{metadata.name}",
            "category": metadata.category,
            "original_name": metadata.name,
            "description": metadata.description,
            "function": metadata.function,
        }
        
        # Add JSON schema if available
        if metadata.input_schema:
            raw_schema = metadata.input_schema.model_json_schema()
            tool_info["input_schema"] = _normalize_schema(raw_schema)
            tool_info["input_model"] = metadata.input_schema
        
        # Add canonical name
        tools.append(tool_info)

    
    return tools


def list_tools() -> None:
    """Print all available tools to stdout."""
    tools = get_all_tools()
    
    print(f"\n📊 Stats Compass MCP Tools ({len(tools)} available)\n")
    print("=" * 60)
    
    # Group by category
    by_category: dict[str, list[dict[str, Any]]] = {}
    for tool in tools:
        cat = tool["category"]
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(tool)
    
    for category, cat_tools in sorted(by_category.items()):
        print(f"\n🔧 {category.upper()} ({len(cat_tools)} tools)")
        print("-" * 40)
        for tool in cat_tools:
            desc = tool["description"][:50] + "..." if len(tool["description"]) > 50 else tool["description"]
            print(f"  • {tool['original_name']}: {desc}")
    
    print("\n" + "=" * 60)
    print("Run 'stats-compass-mcp serve' to start the MCP server.\n")
