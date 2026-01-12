"""
Session management for remote Stats Compass server.

Provides isolated DataFrameState per session, enabling multiple
users to work independently without data leakage.

NOTE: This is single-instance only (in-memory sessions).
For production with multiple workers/containers, sessions would
need Redis or external storage for session metadata + state pointers.
"""

from datetime import datetime
from typing import TYPE_CHECKING, Dict
import logging

from stats_compass_core import DataFrameState

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
        }


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
        
        # Existing session
        if session_id in self._sessions:
            session = self._sessions[session_id]
            session.touch()
            return session
        
        # Check capacity before creating
        if len(self._sessions) >= self.max_sessions:
            self._cleanup_oldest()
        
        # Create new session
        session = Session(
            session_id=session_id,
            memory_limit_mb=self.memory_limit_mb
        )
        self._sessions[session.session_id] = session
        logger.info(f"Created session: {session.session_id}")
        return session
    
    def delete(self, session_id: str) -> bool:
        """
        Delete a session explicitly.
        
        Returns True if deleted, False if not found.
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info(f"Deleted session: {session_id}")
            return True
        return False
    
    def _cleanup_oldest(self) -> None:
        """
        Remove oldest sessions to make room for new ones.
        
        Called when at max_sessions capacity.
        Removes the oldest 10% (minimum 1) by last_active time.
        """
        if not self._sessions:
            return
        
        # Sort by last_active, oldest first
        sorted_sessions = sorted(
            self._sessions.items(),
            key=lambda x: x[1].last_active
        )
        
        # Remove oldest 10% (min 1)
        to_remove = max(1, len(sorted_sessions) // 10)
        
        for sid, _ in sorted_sessions[:to_remove]:
            del self._sessions[sid]
            logger.info(f"Evicted session (capacity): {sid}")
        
        logger.info(f"Evicted {to_remove} sessions for capacity")
    
    def get_stats(self) -> dict:
        """
        Get manager statistics for monitoring/admin.
        
        Returns summary of all active sessions.
        """
        return {
            "active_sessions": len(self._sessions),
            "max_sessions": self.max_sessions,
            "memory_limit_mb_per_session": self.memory_limit_mb,
            "sessions": [
                session.get_info() 
                for session in self._sessions.values()
            ]
        }
    
    def __len__(self) -> int:
        """Return number of active sessions."""
        return len(self._sessions)
    
    def __contains__(self, session_id: str) -> bool:
        """Check if session exists."""
        return session_id in self._sessions


def get_session(ctx: "Context", session_manager: SessionManager) -> Session:
    """
    Get or create a session from the FastMCP context.
    
    This uses FastMCP's MCP session ID (from Streamable HTTP transport)
    to automatically associate each client with their isolated session.
    
    Args:
        ctx: FastMCP Context (injected into tool functions)
        session_manager: The SessionManager instance
    
    Returns:
        Session for this client
    
    Raises:
        ValueError: If no session ID available in context
    """
    session_id = ctx.session_id
    
    if not session_id:
        raise ValueError(
            "No MCP session ID available. This server requires "
            "Streamable HTTP transport with session management."
        )
    
    return session_manager.get_or_create(session_id)
