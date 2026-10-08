"""Checks on names that come from callers and become folder or file names.

A session id names the session's export and upload folders, and an uploaded
file's key names a file inside them. Either one taken as given could climb out
with ``..``, an absolute path or a separator (security scan, 8 Oct 2026). These
checks are the minimum a single path component needs; they do not constrain
the alphabet, because hosted session ids are hashed user ids and existing
folders are named after them.
"""

MAX_NAME_LENGTH = 200


def _single_component(value: object, what: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{what} is required")
    if len(value) > MAX_NAME_LENGTH:
        raise ValueError(f"{what} is too long")
    if value in (".", ".."):
        raise ValueError(f"{what} cannot be '.' or '..'")
    if any(ch in value for ch in ("/", "\\")):
        raise ValueError(f"{what} cannot contain a path separator")
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise ValueError(f"{what} cannot contain control characters")
    return value


def check_session_id(session_id: object) -> str:
    """A session id that can safely name a folder, or ValueError."""
    return _single_component(session_id, "session_id")


def check_file_key(file_key: object) -> str:
    """A plain file name (no folders), or ValueError."""
    return _single_component(file_key, "file_key")


def short_id(session_id: str) -> str:
    """A session id cut short for logs: it identifies a user and unlocks their session."""
    return f"{session_id[:8]}..." if session_id else "-"
