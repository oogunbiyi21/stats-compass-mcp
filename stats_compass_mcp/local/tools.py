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
    Get all MCP-exposed tools from stats-compass-core.
    
    Filters tools by tier:
    - util: Always exposed (load_csv, list_dataframes, etc.)
    - parent: Category controllers (describe_*, execute_*)
    - workflow: High-level pipelines (run_eda_report, run_preprocessing)
    
    Sub-tier tools are NOT exposed directly - they're accessed via execute_* dispatchers.
    
    Returns:
        List of tool metadata dicts with name, category, description, and schema.
    """
    # Ensure tools are discovered
    registry.auto_discover()
    
    tools = []
    # Use list_exposed_tools() which filters to util, parent, workflow tiers
    for metadata in registry.list_exposed_tools():
        # Build MCP tool name:
        # - Parent tools (describe_*, execute_*) already have category context, just use original name
        # - Other tools get category prefix for namespacing
        if metadata.tier == "parent":
            # describe_cleaning, execute_plots, etc. - no prefix needed
            mcp_name = metadata.name
        else:
            # data_load_csv, workflows_run_eda_report, etc.
            mcp_name = f"{metadata.category}_{metadata.name}"
        
        tool_info: dict[str, Any] = {
            "name": mcp_name,
            "category": metadata.category,
            "original_name": metadata.name,
            "description": metadata.description,
            "function": metadata.function,
            "tier": metadata.tier,
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
    """Print all available MCP-exposed tools to stdout."""
    tools = get_all_tools()
    
    print(f"\n📊 Stats Compass MCP Tools ({len(tools)} exposed)\n")
    print("=" * 60)
    
    # Group by tier
    by_tier: dict[str, list[dict[str, Any]]] = {}
    for tool in tools:
        tier = tool.get("tier", "sub")
        if tier not in by_tier:
            by_tier[tier] = []
        by_tier[tier].append(tool)
    
    tier_icons = {"util": "🔧", "parent": "📂", "workflow": "🚀"}
    tier_labels = {
        "util": "UTILITY (always available)",
        "parent": "PARENT (describe/execute dispatchers)",
        "workflow": "WORKFLOW (high-level pipelines)",
    }
    
    for tier in ["util", "parent", "workflow"]:
        tier_tools = by_tier.get(tier, [])
        if not tier_tools:
            continue
        icon = tier_icons.get(tier, "•")
        label = tier_labels.get(tier, tier.upper())
        print(f"\n{icon} {label} ({len(tier_tools)} tools)")
        print("-" * 40)
        for tool in tier_tools:
            desc = tool["description"][:50] + "..." if len(tool["description"]) > 50 else tool["description"]
            print(f"  • {tool['name']}: {desc}")
    
    print("\n" + "=" * 60)
    print("Sub-tools (47) are accessed via execute_* dispatchers.")
    print("Run 'stats-compass-mcp serve' to start the MCP server.\n")
