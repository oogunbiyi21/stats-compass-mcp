"""Tests for tool loading."""

from stats_compass_mcp.tools import get_all_tools


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
