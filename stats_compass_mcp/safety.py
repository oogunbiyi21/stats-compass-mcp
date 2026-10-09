"""Checks on names that come from callers and become folder or file names.

A session id names the session's export and upload folders, and an uploaded
file's key names a file inside them. Either one taken as given could climb out
with ``..``, an absolute path or a separator (security scan, 8 Oct 2026). These
checks are the minimum a single path component needs; they do not constrain
the alphabet, because hosted session ids are hashed user ids and existing
folders are named after them.
"""

import re
from typing import Any, Callable

MAX_NAME_LENGTH = 200
MAX_TOKEN_NAME_LENGTH = 80

# Keys that name a file to write. A served session saves into its own exports
# automatically, so a caller has no business setting them; core confines them
# too, and refusing them here is a second line (re-scan of 0.3.32, F1, F2).
WRITE_PATH_KEYS = frozenset({"save_path", "filepath", "model_save_path"})


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


def find_write_path_keys(value: Any, where: str = "params") -> list[str]:
    """Every WRITE_PATH_KEYS key in ``value``, at any depth, as dotted locations."""
    found: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{where}.{key}"
            if key in WRITE_PATH_KEYS:
                found.append(here)
            found.extend(find_write_path_keys(item, here))
    elif isinstance(value, (list, tuple)):
        for i, item in enumerate(value):
            found.extend(find_write_path_keys(item, f"{where}[{i}]"))
    return found


def refuse_write_paths(value: Any, where: str = "params") -> None:
    """ValueError if ``value`` names a file to write anywhere inside it."""
    found = find_write_path_keys(value, where)
    if found:
        raise ValueError(
            f"{', '.join(found)}: a served session saves to its own exports automatically, "
            "and save paths can't be set. Results that produce files carry a download_url."
        )


def safe_name_token(text: str, default: str = "export") -> str:
    """``text`` as a file-name fragment: [A-Za-z0-9_-] only, capped in length.

    Plot exports are named after workflow steps, and a step's name can carry a
    column name, so ``/`` and ``..`` in a CSV header walked out of the plots
    folder (re-scan of 0.3.32, F3).
    """
    token = re.sub(r"[^A-Za-z0-9_-]", "_", str(text))[:MAX_TOKEN_NAME_LENGTH].strip("_")
    return token or default


# How a session id becomes its folders' name. None keeps the id itself, which
# hosted relies on (its own routes name folders after its hashed user ids).
# `serve` sets an HMAC, because there the session id is the session's
# credential and folder paths reach logs, listings and results (re-scan F5).
_folder_namer: Callable[[str], str] | None = None


def set_session_folder_namer(namer: Callable[[str], str] | None) -> None:
    global _folder_namer
    _folder_namer = namer


def session_folder(session_id: str) -> str:
    """The folder name for a session: checked, then named by the namer if one is set."""
    check_session_id(session_id)
    return check_session_id(_folder_namer(session_id)) if _folder_namer else session_id
