"""
Session management for Stats Compass MCP server.

Provides isolated DataFrameState per session, enabling multiple
users to work independently without data leakage.

For local/stdio transport: Only one session exists (the default).
For remote/HTTP transport: Multiple sessions, one per MCP session ID.

NOTE: This is single-instance only (in-memory sessions).
For production with multiple workers/containers, sessions would
need Redis or external storage for session metadata + state pointers.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Dict
import logging

from stats_compass_core import DataFrameState

from stats_compass_mcp.exports import (
    get_exports_dir,
    ensure_exports_dir,
    get_export_path,
    get_download_url,
    cleanup_session_exports,
    list_session_exports,
    ExportCategory,
)

if TYPE_CHECKING:
    from fastmcp import Context

logger = logging.getLogger(__name__)


class Session:
    """
    Isolated session with its own DataFrameState.
    
    Each session has:
    - Unique session_id (from FastMCP's MCP transport)
    - Isolated DataFrameState (DataFrames + trained models)
    - Timestamps for expiry management
    - Optional metadata
    """
    
    def __init__(self, session_id: str, memory_limit_mb: float = 500.0):
        """
        Initialize a session.
        
        Args:
            session_id: Required - the MCP session ID from FastMCP.
            memory_limit_mb: Memory limit for this session's DataFrameState.
        """
        if not session_id:
            raise ValueError("session_id is required")
        self.session_id = session_id
        self.state = DataFrameState(memory_limit_mb=memory_limit_mb)
        self.created_at = datetime.now()
        self.last_active = datetime.now()
        self.metadata: dict = {}
    
    def touch(self) -> None:
        """Update last active timestamp."""
        self.last_active = datetime.now()
    
    def get_info(self) -> dict:
        """Get session info for API responses."""
        dataframes = self.state.list_dataframes()
        
        return {
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat(),
            "dataframes": [
                {
                    "name": df.name,
                    "shape": list(df.shape),
                    "columns": len(df.columns)
                }
                for df in dataframes
            ],
            "dataframe_count": len(dataframes),
            "model_count": len(self.state._models),
            "models": list(self.state._models.keys()),
            "exports": list_session_exports(self.session_id),
        }
    
    def export_path(self, category: ExportCategory, filename: str) -> str:
        """
        Get the full path for an export file.
        
        Args:
            category: Category (models, data, plots, timeseries)
            filename: The filename
        
        Returns:
            Full path as string
        """
        return str(get_export_path(self.session_id, category, filename))
    
    def download_url(self, category: ExportCategory, filename: str) -> str:
        """
        Get download URL for an exported file.
        
        Args:
            category: Category (models, data, plots, timeseries)
            filename: The filename
        
        Returns:
            Download URL, or empty string if not in remote mode
        """
        return get_download_url(self.session_id, category, filename)
    
    def cleanup_exports(self) -> None:
        """Clean up all exported files for this session."""
        cleanup_session_exports(self.session_id)


class SessionManager:
    """
    Manages multiple isolated sessions.
    
    This is in-memory, single-instance only.
    
    Features:
    - Create/retrieve sessions by ID
    - Capacity management (evict oldest when full)
    - Statistics for monitoring
    
    Note: Sessions are evicted when capacity is reached (oldest first).
    There is no TTL-based expiry - for that, add a background scheduler
    or use Redis with built-in TTL.
    """
    
    def __init__(
        self, 
        memory_limit_mb: float = 500.0, 
        max_sessions: int = 100
    ):
        self._sessions: Dict[str, Session] = {}
        self.memory_limit_mb = memory_limit_mb
        self.max_sessions = max_sessions
        
        logger.info(
            f"SessionManager initialized: memory_limit={memory_limit_mb}MB, "
            f"max_sessions={max_sessions}"
        )
    
    def get_or_create(self, session_id: str) -> Session:
        """
        Get existing session or create new one.
        
        Args:
            session_id: Required MCP session ID from FastMCP.
        
        Returns:
            Session instance
        
        Raises:
            ValueError: If session_id is not provided.
        """
        if not session_id:
            raise ValueError("session_id is required")
        
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.touch()
            return session
        
        # Check capacity and evict if needed
        if len(self._sessions) >= self.max_sessions:
            self._evict_oldest()
        
        # Create new session
        session = Session(session_id, self.memory_limit_mb)
        self._sessions[session_id] = session
        logger.info(f"Created new session: {session_id}")
        return session
    
    def get(self, session_id: str) -> Session | None:
        """Get session by ID (returns None if not found)."""
        session = self._sessions.get(session_id)
        if session:
            session.touch()
        return session
    
    def delete(self, session_id: str) -> bool:
        """Delete a session and cleanup its exports. Returns True if deleted."""
        if session_id in self._sessions:
            # Cleanup exports first
            self._sessions[session_id].cleanup_exports()
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False
    
    def _evict_oldest(self) -> None:
        """Evict the oldest session by last_active timestamp."""
        if not self._sessions:
            return
        
        oldest_id = min(
            self._sessions.keys(),
            key=lambda k: self._sessions[k].last_active
        )
        # Cleanup exports before evicting
        self._sessions[oldest_id].cleanup_exports()
        del self._sessions[oldest_id]
        logger.info(f"Evicted oldest session: {oldest_id}")
    
    def get_stats(self) -> dict:
        """Get statistics for monitoring."""
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self.max_sessions,
            "memory_limit_per_session_mb": self.memory_limit_mb,
            "sessions": [
                {
                    "session_id": s.session_id[:8] + "...",  # Truncate for privacy
                    "created_at": s.created_at.isoformat(),
                    "last_active": s.last_active.isoformat(),
                    "dataframe_count": len(s.state.list_dataframes()),
                    "model_count": len(s.state._models),
                }
                for s in self._sessions.values()
            ]
        }


def get_session(ctx: "Context", session_manager: SessionManager) -> Session:
    """
    Get or create session from FastMCP context.
    
    Uses the MCP session ID from the context.
    
    Args:
        ctx: FastMCP Context object
        session_manager: SessionManager instance
    
    Returns:
        Session instance
    """
    # FastMCP provides session_id in context
    session_id = getattr(ctx, "session_id", None) or getattr(ctx, "_session_id", None)
    
    if not session_id:
        # Try to get from request ID as fallback
        request_id = getattr(ctx, "request_id", None)
        if request_id:
            session_id = f"session-{request_id}"
        else:
            # Default session for local/stdio
            session_id = "default"
    
    return session_manager.get_or_create(session_id)
