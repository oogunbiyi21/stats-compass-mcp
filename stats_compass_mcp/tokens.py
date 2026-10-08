"""Signed, expiring tokens for upload and download links.

The links used to carry the raw session id, the session's only credential, so
one link in a shared transcript or a proxy log handed over the session, and the
routes trusted it to decide where files were read and written (security scan,
8 Oct 2026, F2, F4, F6, F7). A token names what it is for and expires; the
session id inside it is signed, not readable as a credential on its own.

The key is STATS_COMPASS_SECRET_KEY, or a random one per process when that is
unset, in which case links stop working when the server restarts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

MAX_TOKEN_LENGTH = 2048
DEFAULT_TTL_SECONDS = 3600

_SECRET = (os.getenv("STATS_COMPASS_SECRET_KEY") or secrets.token_hex(32)).encode()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(payload: str) -> str:
    return _b64(hmac.new(_SECRET, payload.encode(), hashlib.sha256).digest())


def make_token(
    purpose: str,
    session_id: str,
    category: str = "",
    filename: str = "",
    ttl: int = DEFAULT_TTL_SECONDS,
) -> str:
    """A token for ``purpose`` ("upload" or "download"), valid for ``ttl`` seconds."""
    body = [purpose, session_id, category, filename, int(time.time()) + int(ttl)]
    payload = _b64(json.dumps(body, separators=(",", ":")).encode())
    return f"{payload}.{_sign(payload)}"


def read_token(token: str, purpose: str) -> dict | None:
    """The token's fields if it is genuine, unexpired and for ``purpose``; else None."""
    if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH or token.count(".") != 1:
        return None
    payload, signature = token.split(".")
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        kind, session_id, category, filename, expires = json.loads(_unb64(payload))
    except (ValueError, TypeError):
        return None
    if kind != purpose or not isinstance(expires, int) or expires < time.time():
        return None
    return {"session_id": session_id, "category": category, "filename": filename}
