"""Tests for Stats Compass MCP server."""

import pytest
from stats_compass_mcp.server import create_mcp_server
from stats_compass_mcp.session import Session, SessionManager


class TestSession:
    """Tests for session management."""
    
    def test_session_creation(self):
        """Test that sessions can be created."""
        session = Session("test-session-1")
        assert session.session_id == "test-session-1"
        assert session.state is not None
    
    def test_session_info(self):
        """Test session info retrieval."""
        session = Session("test-session-2")
        info = session.get_info()
        assert "dataframes" in info
        assert "created_at" in info
        assert info["dataframe_count"] == 0

    def test_session_info_omits_session_id(self):
        """The session id is the hashed user id in hosted mode, so it must not be
        returned into the assistant's conversation context."""
        info = Session("test-session-3").get_info()
        assert "session_id" not in info
        assert "test-session-3" not in str(info)


class TestSessionManager:
    """Tests for SessionManager."""
    
    def test_get_or_create(self):
        """Test session creation and retrieval."""
        manager = SessionManager(max_sessions=10)
        
        # Create new session
        session1 = manager.get_or_create("session-1")
        assert session1.session_id == "session-1"
        
        # Get same session
        session2 = manager.get_or_create("session-1")
        assert session1 is session2
        
        # Create different session
        session3 = manager.get_or_create("session-2")
        assert session3.session_id == "session-2"
        assert session3 is not session1
    
    def test_max_sessions_eviction(self):
        """Test that old sessions are evicted when limit reached."""
        manager = SessionManager(max_sessions=2)
        
        manager.get_or_create("session-1")
        manager.get_or_create("session-2")
        
        # This should evict session-1
        manager.get_or_create("session-3")
        
        assert manager.get("session-1") is None
        assert manager.get("session-2") is not None
        assert manager.get("session-3") is not None
    
    def test_stats(self):
        """Test server stats retrieval."""
        manager = SessionManager(max_sessions=10)
        manager.get_or_create("session-1")
        
        stats = manager.get_stats()
        assert stats["active_sessions"] == 1
        assert stats["max_sessions"] == 10


class TestServerCreation:
    """Tests for server creation."""
    
    def test_create_server(self):
        """Test that server can be created."""
        mcp = create_mcp_server()
        assert mcp is not None
        assert mcp.name == "stats-compass"
    
    def test_server_has_tools(self):
        """Test that server can be created and has a tool manager."""
        mcp = create_mcp_server()
        
        # FastMCP stores tools in _tool_manager
        assert hasattr(mcp, '_tool_manager'), "Server should have tool manager"
        # Tools are registered - actual tool list is async, so just verify manager exists


class TestSmokeTests:
    """Smoke tests to verify basic functionality works."""
    
    def test_session_with_dataframe(self):
        """Test loading data into a session."""
        import pandas as pd
        
        session = Session("smoke-test-1")
        
        # Create a simple DataFrame
        df = pd.DataFrame({"a": [1, 2, 3], "b": [4, 5, 6]})
        session.state.set_dataframe(df, name="test_df", operation="test")
        
        # Verify it's stored
        dataframes = session.state.list_dataframes()
        assert len(dataframes) == 1
        assert dataframes[0].name == "test_df"
    
    def test_session_isolation(self):
        """Test that sessions are isolated."""
        import pandas as pd
        
        manager = SessionManager(max_sessions=10)
        
        session1 = manager.get_or_create("isolation-test-1")
        session2 = manager.get_or_create("isolation-test-2")
        
        # Add DataFrame to session1
        df = pd.DataFrame({"x": [1, 2, 3]})
        session1.state.set_dataframe(df, name="session1_df", operation="test")
        
        # Session2 should not see it
        assert len(session1.state.list_dataframes()) == 1
        assert len(session2.state.list_dataframes()) == 0
