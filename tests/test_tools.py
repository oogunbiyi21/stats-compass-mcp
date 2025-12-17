"""Tests for tool loading."""

from stats_compass_mcp.tools import get_all_tools


def _find_array_nodes_without_items(schema: dict) -> list[str]:
    """Return paths of array schemas that do not declare `items`."""
    missing: list[str] = []

    def walk(node, path=""):
        if isinstance(node, dict):
            if node.get("type") == "array" and not node.get("items"):
                missing.append(path or "<root>")
            for key, value in node.items():
                walk(value, f"{path}/{key}" if path else key)
        elif isinstance(node, list):
            for idx, value in enumerate(node):
                walk(value, f"{path}[{idx}]")

    walk(schema)
    return missing


def test_tools_load() -> None:
    """Test that tools can be loaded from stats-compass-core."""
    tools = get_all_tools()
    assert len(tools) > 0, "Should have at least one tool"


def test_tools_have_required_fields() -> None:
    """Test that all tools have required metadata."""
    tools = get_all_tools()
    
    for tool in tools:
        assert "name" in tool, f"Tool missing 'name': {tool}"
        assert "category" in tool, f"Tool missing 'category': {tool}"
        assert "function" in tool, f"Tool missing 'function': {tool}"
        assert callable(tool["function"]), f"Tool function not callable: {tool['name']}"


def test_tools_have_categories() -> None:
    """Test that tools are organized into expected categories."""
    tools = get_all_tools()
    
    categories = {t["category"] for t in tools}
    
    # Should have at least data and eda categories
    assert "data" in categories, "Missing 'data' category"
    assert "eda" in categories or "cleaning" in categories, "Missing basic analysis categories"


def test_tool_schemas_have_array_items() -> None:
    """All tool schemas should declare `items` for arrays (required by some clients)."""
    tools = get_all_tools()
    for tool in tools:
        schema = tool.get("input_schema", {})
        missing_items_paths = _find_array_nodes_without_items(schema)
        assert not missing_items_paths, f"{tool['name']} has arrays without items: {missing_items_paths}"
