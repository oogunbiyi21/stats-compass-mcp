"""Each served session reads and writes only its own folders (security scan, 8 Oct 2026).

stats-compass-mcp F1, F5, F8 (load_csv, load_excel and list_files read any host
path), F9 and F10 (save_csv and save_model honoured absolute paths unless
STATS_COMPASS_SERVER_URL happened to be set), F11 (server_stats listed every
session to anyone), and register_uploaded_file joining a caller's file key to
the upload folder as given.

A SessionManager now confines its sessions by default, through core's
FilePolicy: writes go to the session's exports folder, reads come from its
uploads folder. Only the local stdio server opts out, because there the paths
are the user's own.
"""

import asyncio
import os
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastmcp import FastMCP
from stats_compass_core.utils.file_safety import UnsafePathError

from stats_compass_mcp import exports
from stats_compass_mcp.server import create_mcp_server
from stats_compass_mcp.session import Session, SessionManager
from stats_compass_mcp.storage import LocalStorageBackend
from stats_compass_mcp.tools import register_all_tools


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    out = {name: tmp_path / name for name in ("exports", "uploads", "elsewhere")}
    for path in out.values():
        path.mkdir()
    (out["elsewhere"] / "secret.csv").write_text("key\nhunter2\n")
    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", out["exports"])
    monkeypatch.setattr(exports, "UPLOADS_BASE_DIR", out["uploads"])
    monkeypatch.delenv("STATS_COMPASS_SERVER_URL", raising=False)
    monkeypatch.delenv("STATS_COMPASS_WRITE_ROOT", raising=False)
    monkeypatch.delenv("STATS_COMPASS_READ_ROOTS", raising=False)
    return out


def _tools(mcp):
    return asyncio.run(mcp._tool_manager.get_tools())


def _server(dirs, *, confine=True, admin=False):
    mcp = FastMCP("test")
    manager = SessionManager(confine_files=confine)
    storage = LocalStorageBackend(base_path=str(dirs["uploads"]))
    register_all_tools(mcp, manager, storage=storage, include_admin=admin)
    return _tools(mcp), manager


CTX = SimpleNamespace(session_id="s1")


def _call(tools, name, **kwargs):
    return tools[name].fn(ctx=CTX, **kwargs)


def _session_with_frame(manager):
    session = manager.get_or_create("s1")
    session.state.set_dataframe(pd.DataFrame({"a": [1, 2]}), "t", "test")
    return session


class TestSessionsAreConfinedByDefault:
    def test_the_policy_names_the_session_folders(self, dirs):
        state = SessionManager().get_or_create("s1").state
        assert state.file_policy.write_root == dirs["exports"] / "s1"
        assert state.file_policy.read_roots == (dirs["uploads"] / "s1",)

    def test_a_local_server_is_not_confined(self, dirs):
        state = SessionManager(confine_files=False).get_or_create("s1").state
        assert state.file_policy.write_root is None and state.file_policy.read_roots is None

    def test_stdio_opts_out_and_http_does_not(self, dirs):
        local = create_mcp_server(local=True)
        served = create_mcp_server()
        assert "server_stats" in _tools(local)
        assert "server_stats" not in _tools(served)


class TestReadsStayInTheSessionsUploads:
    def test_load_csv_outside_is_refused(self, dirs):
        tools, _ = _server(dirs)
        with pytest.raises(UnsafePathError):
            _call(tools, "load_csv", path=str(dirs["elsewhere"] / "secret.csv"))

    def test_load_csv_inside_works_by_name(self, dirs):
        tools, _ = _server(dirs)
        (dirs["uploads"] / "s1").mkdir()
        (dirs["uploads"] / "s1" / "orders.csv").write_text("a\n1\n")
        result = _call(tools, "load_csv", path="orders.csv")
        assert result["dataframe_name"] == "orders"

    def test_list_files_outside_is_refused(self, dirs):
        tools, _ = _server(dirs)
        with pytest.raises(UnsafePathError):
            _call(tools, "list_files", directory=str(dirs["elsewhere"]))

    def test_another_sessions_uploads_are_out_of_reach(self, dirs):
        tools, _ = _server(dirs)
        (dirs["uploads"] / "s2").mkdir()
        (dirs["uploads"] / "s2" / "theirs.csv").write_text("a\n1\n")
        with pytest.raises(UnsafePathError):
            _call(tools, "load_csv", path=str(dirs["uploads"] / "s2" / "theirs.csv"))


class TestWritesStayInTheSessionsExports:
    def test_save_csv_ignores_an_absolute_path_without_the_url_variable(self, dirs):
        """F9/F10: confinement no longer depends on STATS_COMPASS_SERVER_URL."""
        tools, manager = _server(dirs)
        _session_with_frame(manager)
        result = _call(tools, "save_csv", dataframe_name="t", filepath=str(dirs["elsewhere"] / "planted.csv"))
        # 0.3.34: a served session's result names the file, not its server path (re-scan F6)
        assert result["filepath"] == "planted.csv"
        assert (dirs["exports"] / "s1" / "data" / "planted.csv").exists()
        assert sorted(p.name for p in dirs["elsewhere"].iterdir()) == ["secret.csv"]

    def test_save_model_too(self, dirs):
        tools, manager = _server(dirs)
        session = _session_with_frame(manager)
        model_id = session.state.store_model({"w": 1}, "toy", "a", [], "t")
        result = _call(tools, "save_model", model_id=model_id, filepath="~/model.joblib")
        # 0.3.34: the result names the file; it is written in the session's models folder
        assert result["filepath"] == "model.joblib"
        assert (dirs["exports"] / "s1" / "models" / "model.joblib").exists()

    def test_the_download_link_names_the_file_actually_written(self, dirs, monkeypatch):
        """Core never overwrites; a second save is x_1.csv and the link must say so."""
        monkeypatch.setattr(exports, "_download_url_builder", lambda s, c, f: f"https://h/{c}/{f}")
        tools, manager = _server(dirs)
        _session_with_frame(manager)
        _call(tools, "save_csv", dataframe_name="t", filepath="x.csv")
        second = _call(tools, "save_csv", dataframe_name="t", filepath="x.csv")
        assert second["download_url"] == "https://h/data/x_1.csv"

    def test_a_local_server_writes_where_the_user_says(self, dirs):
        tools, manager = _server(dirs, confine=False)
        _session_with_frame(manager)
        target = dirs["elsewhere"] / "mine.csv"
        result = _call(tools, "save_csv", dataframe_name="t", filepath=str(target))
        assert Path(result["filepath"]) == target.resolve()


class TestUploadedFileKeys:
    @pytest.mark.parametrize("key", ["../s2/theirs.csv", "../../elsewhere/secret.csv", "/etc/hosts", "..", "a\\b.csv"])
    def test_register_refuses_anything_but_a_plain_name(self, dirs, key):
        tools, _ = _server(dirs)
        (dirs["uploads"] / "s2").mkdir()
        (dirs["uploads"] / "s2" / "theirs.csv").write_text("a\n1\n")
        result = _call(tools, "register_uploaded_file", file_key=key)
        assert "error" in result

    def test_register_loads_a_plain_name(self, dirs):
        tools, _ = _server(dirs)
        (dirs["uploads"] / "s1").mkdir()
        (dirs["uploads"] / "s1" / "orders.csv").write_text("a\n1\n")
        assert _call(tools, "register_uploaded_file", file_key="orders.csv")["success"]


class TestServerStats:
    def test_not_registered_unless_asked(self, dirs):
        tools, _ = _server(dirs)
        assert "server_stats" not in tools

    def test_registered_for_a_local_operator(self, dirs):
        tools, _ = _server(dirs, admin=True)
        assert "server_stats" in tools


class TestSessionIds:
    @pytest.mark.parametrize("bad", ["..", ".", "a/b", "a\\b", "x\x00y", "", "a" * 300, "line\nbreak"])
    def test_a_session_id_that_cannot_name_a_folder_is_refused(self, bad):
        with pytest.raises(ValueError):
            Session(bad)

    @pytest.mark.parametrize("good", ["s1", "f3a9c2e1d4b5", "auth0|abc123", "session-42"])
    def test_ids_in_use_still_work(self, dirs, good):
        Session(good)
