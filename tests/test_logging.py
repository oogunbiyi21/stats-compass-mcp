"""Logs go to stderr, and never hold a whole session id (security scan, 8 Oct 2026, F12).

The CLI used to send the root logger at DEBUG to a fixed, world-readable
/tmp/stats_compass_mcp_debug.log, and the session code logged full session ids,
which are the sessions' credentials; /download's traversal could read that file
remotely. Now: stderr at INFO, a file only where STATS_COMPASS_LOG_FILE says,
created readable by its owner alone, and session ids cut short.
"""

import logging
import os
import stat
from pathlib import Path

import pytest

from stats_compass_mcp import cli
from stats_compass_mcp.session import SessionManager
from stats_compass_mcp.storage import LocalStorageBackend

LONG_ID = "f3a9c2e1d4b5a6978877665544332211"


@pytest.fixture
def fresh_root():
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    root.handlers = []
    yield root
    for handler in root.handlers:
        handler.close()
    root.handlers, root.level = saved


def test_no_file_unless_asked(fresh_root, monkeypatch):
    monkeypatch.delenv("STATS_COMPASS_LOG_FILE", raising=False)
    cli.configure_logging()
    assert fresh_root.level == logging.INFO
    assert not any(isinstance(h, logging.FileHandler) for h in fresh_root.handlers)


def test_a_requested_file_is_private(fresh_root, monkeypatch, tmp_path):
    path = tmp_path / "mcp.log"
    monkeypatch.setenv("STATS_COMPASS_LOG_FILE", str(path))
    cli.configure_logging()
    logging.getLogger("x").info("hello")
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_importing_the_cli_does_not_configure_logging():
    """It used to call basicConfig at import, before anyone chose anything."""
    source = Path(cli.__file__).read_text()
    assert "/tmp/stats_compass_mcp_debug.log" not in source
    assert "basicConfig(" not in source.split("def configure_logging")[0]


def test_session_ids_are_cut_short(caplog, tmp_path, monkeypatch):
    from stats_compass_mcp import exports

    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", tmp_path / "exports")
    with caplog.at_level(logging.DEBUG):
        manager = SessionManager(max_sessions=1)
        manager.get_or_create(LONG_ID)
        manager.get_or_create("another-session-id-that-evicts")
        manager.delete("another-session-id-that-evicts")
        storage = LocalStorageBackend(base_path=str(tmp_path / "uploads"))
        (tmp_path / "uploads" / LONG_ID).mkdir(parents=True)
        (tmp_path / "uploads" / LONG_ID / "x.csv").write_text("a\n")
        storage.delete_session_files(LONG_ID)
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert LONG_ID[:8] in text
    assert LONG_ID not in text
    assert "another-session-id-that-evicts" not in text
