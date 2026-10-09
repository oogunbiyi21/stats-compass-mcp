"""Encrypted, expiring tokens for upload and download links.

The links used to carry the raw session id, the session's only credential, so
one link in a shared transcript or a proxy log handed over the session, and the
routes trusted it to decide where files were read and written (security scan,
8 Oct 2026, F2, F4, F6, F7). A token names what it is for, the session, the
folder and the file, and when it expires.

It is encrypted and authenticated (Fernet: AES-128-CBC with HMAC-SHA256), not
just signed. A signed token's payload is only base64, so decoding a shared link
gave the session id back (pre-release review F1, 8 Oct 2026). Nothing in a
token is readable without the key, and a changed token is refused.

The key is derived from STATS_COMPASS_SECRET_KEY, or from a random secret per
process when that is unset, in which case links stop working when the server
restarts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from cryptography.fernet import Fernet, InvalidToken

MAX_TOKEN_LENGTH = 2048
DEFAULT_TTL_SECONDS = 3600

# Read once, at import: a deployment must set the variable before this module
# loads. KEY_SOURCE says which happened, so a server can log it.
KEY_SOURCE = "environment" if os.getenv("STATS_COMPASS_SECRET_KEY") else "generated"
_SECRET = (os.getenv("STATS_COMPASS_SECRET_KEY") or secrets.token_hex(32)).encode()
_FERNET = Fernet(
    base64.urlsafe_b64encode(hashlib.sha256(b"stats-compass-mcp link tokens v2|" + _SECRET).digest())
)


def make_token(
    purpose: str,
    session_id: str,
    category: str = "",
    filename: str = "",
    ttl: int = DEFAULT_TTL_SECONDS,
) -> str:
    """A token for ``purpose`` ("upload" or "download"), valid for ``ttl`` seconds."""
    body = [purpose, session_id, category, filename, int(time.time()) + int(ttl)]
    return _FERNET.encrypt(json.dumps(body, separators=(",", ":")).encode()).decode()


def read_token(token: str, purpose: str) -> dict | None:
    """The token's fields if it is genuine, unexpired and for ``purpose``; else None."""
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH:
        return None
    try:
        kind, session_id, category, filename, expires = json.loads(_FERNET.decrypt(token.encode()))
    except (InvalidToken, ValueError, TypeError):
        return None
    if kind != purpose or not isinstance(expires, int) or expires < time.time():
        return None
    return {"session_id": session_id, "category": category, "filename": filename}


def folder_name(session_id: str) -> str:
    """An opaque, stable folder name for a session: HMAC-SHA256 of its id under the key.

    The session id is the session's credential in `serve`, and folder paths
    appear in logs, listings and tool results (re-scan of 0.3.32, F5).
    """
    digest = hmac.new(_SECRET, b"stats-compass-mcp session folder v1|" + session_id.encode(), hashlib.sha256)
    return digest.hexdigest()[:32]
