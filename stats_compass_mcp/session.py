"""
Session management for Stats Compass MCP server.

Provides isolated DataFrameState per session, enabling multiple
users to work independently without data leakage.

For local/stdio transport: Only one session exists (the default).
For remote/HTTP transport: Multiple sessions, one per MCP session ID.

NOTE: This is single-instance only (in-memory sessions).
For production with multiple workers/containers, sessions would
need Redis or external storage for session metadata + state pointers.

Idle sessions are removed by ``SessionManager.evict_idle``: the HTTP server
runs it on a timer (``start_idle_sweeper``), and a server embedding the tools
(hosted) calls it from its own sweeper. A session in the middle of a tool
call is never removed (``SessionActivityMiddleware``).
"""

import logging
import os
import threading
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Iterator

from fastmcp.server.middleware import Middleware

from stats_compass_core import DataFrameState
from stats_compass_core.utils.file_safety import FilePolicy

from stats_compass_mcp import exports
from stats_compass_mcp.exports import (
    ExportCategory,
    cleanup_session_exports,
    get_download_url,
    get_export_path,
    list_session_exports,
)
from stats_compass_mcp.safety import check_session_id, session_folder, short_id

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

    def __init__(self, session_id: str, memory_limit_mb: float = 500.0, confine_files: bool = True):
        """
        Initialize a session.
        
        Args:
            session_id: Required - the MCP session ID from FastMCP. It names the
                session's folders, so it must be a single safe path component.
            memory_limit_mb: Memory limit for this session's DataFrameState.
            confine_files: Writes go only to this session's exports folder and
                reads come only from its uploads folder (core's FilePolicy).
                On by default: a served session's paths come from whoever
                calls the tools (security scan, 8 Oct 2026). Only the local
                stdio server turns it off, where the paths are the user's own.
        """
        self.session_id = check_session_id(session_id)
        self.confined = confine_files
        policy = (
            FilePolicy(
                write_root=exports.EXPORTS_BASE_DIR / session_folder(session_id),
                read_roots=(exports.UPLOADS_BASE_DIR / session_folder(session_id),),
            )
            if confine_files
            else None
        )
        self.state = DataFrameState(memory_limit_mb=memory_limit_mb, file_policy=policy)
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
    - Idle expiry (``evict_idle``), never of a session in the middle of a call
    - Statistics for monitoring
    - Optional session_id_resolver for custom session identity (e.g. JWT sub claim)

    Thread-safe: tool calls may run in worker threads, and an embedding
    server's sweeper calls ``evict_idle`` from another.
    """

    def __init__(
        self,
        memory_limit_mb: float = 500.0,
        max_sessions: int = 100,
        session_id_resolver=None,
        *,
        confine_files: bool = True,
    ):
        self._sessions: Dict[str, Session] = {}
        # Re-entrant: get_or_create evicts under the same lock.
        self._lock = threading.RLock()
        # Tool calls under way, per session id (SessionActivityMiddleware).
        self._in_use: Counter[str] = Counter()
        self.memory_limit_mb = memory_limit_mb
        self.max_sessions = max_sessions
        self._session_id_resolver = session_id_resolver
        self.confine_files = confine_files

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

        with self._lock:
            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.touch()
                return session

            # Check capacity and evict if needed
            if len(self._sessions) >= self.max_sessions:
                self._evict_oldest()

            # Create new session
            session = Session(session_id, self.memory_limit_mb, confine_files=self.confine_files)
            self._sessions[session_id] = session
        logger.info(f"Created new session: {short_id(session_id)}")
        return session

    def get(self, session_id: str) -> Session | None:
        """Get session by ID (returns None if not found)."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session:
                session.touch()
            return session

    def delete(self, session_id: str) -> bool:
        """Delete a session and cleanup its exports. Returns True if deleted."""
        with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return False
        session.cleanup_exports()
        logger.info(f"Deleted session: {short_id(session_id)}")
        return True

    @contextmanager
    def in_use(self, session_id: str) -> Iterator[None]:
        """Mark a session as in a call: neither idle expiry nor capacity eviction removes it.

        Counts, so overlapping calls on one session nest. On the way out the
        session (if it exists) is touched, so its idle time runs from the end
        of the call, not the start. Creates nothing.
        """
        with self._lock:
            self._in_use[session_id] += 1
        try:
            yield
        finally:
            with self._lock:
                self._in_use[session_id] -= 1
                if self._in_use[session_id] <= 0:
                    del self._in_use[session_id]
                session = self._sessions.get(session_id)
                if session:
                    session.touch()

    def evict_idle(self, max_idle: timedelta | float, *, now: datetime | None = None) -> int:
        """Remove every session idle for longer than ``max_idle``, unless it is in a call.

        Its dataframes and models go with it, and its exports folder is
        deleted, as ``delete`` does. ``max_idle`` is a timedelta, or seconds.
        Returns how many were removed. Safe to call from another thread while
        tool calls run.

        Raises ValueError when ``max_idle`` is zero or less: a mis-set setting
        must not empty every session on each sweep.
        """
        if not isinstance(max_idle, timedelta):
            max_idle = timedelta(seconds=float(max_idle))
        if max_idle <= timedelta(0):
            raise ValueError(f"max_idle must be positive, got {max_idle}")
        cutoff = (now or datetime.now()) - max_idle
        with self._lock:
            idle = [
                sid for sid, s in self._sessions.items()
                if s.last_active < cutoff and self._in_use.get(sid, 0) == 0
            ]
            removed = [self._sessions.pop(sid) for sid in idle]
        # Files outside the lock: deleting them can be slow, and the sessions
        # are already out of the table, so no call can reach them.
        for session in removed:
            try:
                session.cleanup_exports()
            except Exception as e:
                logger.warning(f"Could not clean up an idle session's exports: {e}")
        if removed:
            # A count only: session ids are credentials in some deployments.
            logger.info(f"Removed {len(removed)} idle session(s) (idle over {max_idle})")
        return len(removed)

    def _evict_oldest(self) -> None:
        """Evict the oldest session by last_active timestamp, skipping any in a call.

        With every session in a call, nothing is evicted and the new session is
        admitted over capacity: refusing it would fail a user's call outright.
        """
        with self._lock:
            candidates = [k for k in self._sessions if self._in_use.get(k, 0) == 0]
            if not candidates:
                return
            oldest_id = min(candidates, key=lambda k: self._sessions[k].last_active)
            session = self._sessions.pop(oldest_id)
        session.cleanup_exports()
        logger.info(f"Evicted oldest session: {short_id(oldest_id)}")

    def get_stats(self) -> dict:
        """Get statistics for monitoring."""
        with self._lock:
            sessions = list(self._sessions.values())
        return {
            "active_sessions": len(sessions),
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
                for s in sessions
            ]
        }


class SessionActivityMiddleware(Middleware):
    """Marks a tool call's session as in use for the length of the call.

    Added by ``register_all_tools``. Middleware is server-wide, so it covers an
    embedding server's own tools too. The session id is resolved the way
    ``get_session`` resolves it; if that fails here, the call runs unmarked and
    the tool reports the problem itself.
    """

    def __init__(self, session_manager: SessionManager):
        self.session_manager = session_manager

    async def on_call_tool(self, context, call_next):
        ctx = context.fastmcp_context
        try:
            session_id = resolve_session_id(ctx, self.session_manager) if ctx is not None else None
        except Exception:
            session_id = None
        if not session_id:
            return await call_next(context)
        with self.session_manager.in_use(session_id):
            return await call_next(context)


IDLE_HOURS_ENV = "STATS_COMPASS_SESSION_IDLE_HOURS"
DEFAULT_IDLE_HOURS = 24.0
SWEEP_EVERY_SECONDS = 15 * 60


def idle_expiry_from_env() -> timedelta | None:
    """The served server's idle expiry: 24 hours, or ``STATS_COMPASS_SESSION_IDLE_HOURS``; 0 turns it off."""
    raw = os.getenv(IDLE_HOURS_ENV, "").strip()
    try:
        hours = float(raw) if raw else DEFAULT_IDLE_HOURS
    except ValueError:
        logger.warning(f"{IDLE_HOURS_ENV}={raw!r} is not a number; using {DEFAULT_IDLE_HOURS} hours")
        hours = DEFAULT_IDLE_HOURS
    return timedelta(hours=hours) if hours > 0 else None


def start_idle_sweeper(
    session_manager: SessionManager, max_idle: timedelta, every: float = SWEEP_EVERY_SECONDS
) -> threading.Event:
    """Run ``evict_idle(max_idle)`` every ``every`` seconds on a daemon thread.

    Returns an event that stops it when set. A failed sweep is logged and the
    next one runs as usual.
    """
    stop = threading.Event()

    def sweep() -> None:
        while not stop.wait(every):
            try:
                session_manager.evict_idle(max_idle)
            except Exception as e:
                logger.warning(f"Idle session sweep failed: {e}")

    threading.Thread(target=sweep, name="stats-compass-idle-sweeper", daemon=True).start()
    return stop


def get_session(ctx: "Context", session_manager: SessionManager) -> Session:
    """
    Get or create session from FastMCP context.

    If the SessionManager has a session_id_resolver, it is called with the
    context to determine the session ID. Otherwise, the MCP session ID from
    the context is used.

    Args:
        ctx: FastMCP Context object
        session_manager: SessionManager instance

    Returns:
        Session instance
    """
    return session_manager.get_or_create(resolve_session_id(ctx, session_manager))


def resolve_session_id(ctx: Any, session_manager: SessionManager) -> str:
    """The session id a tool call belongs to: the resolver's, else the MCP session's."""
    # Use custom resolver if provided (e.g. JWT sub claim in hosted mode).
    # Session ids identify a user, so they are logged at debug, never info.
    if session_manager._session_id_resolver:
        session_id = session_manager._session_id_resolver(ctx)
        logger.debug("Resolved session_id via custom resolver")
        return session_id

    # FastMCP provides session_id as a property that reads from mcp-session-id header
    try:
        session_id = ctx.session_id
        logger.debug("Resolved session_id from ctx.session_id")
    except Exception as e:
        logger.warning(f"Failed to get ctx.session_id: {e}")
        session_id = None

    if not session_id:
        # Fallback: try request_id
        try:
            request_id = ctx.request_id
            session_id = f"session-{request_id}"
            logger.debug("Fell back to request_id for session_id")
        except Exception:
            # Default session for local/stdio
            session_id = "default"
            logger.debug("Using default session")

    return session_id
