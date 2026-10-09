"""Fixes for the re-scan of 0.3.32 (9 October 2026), released in 0.3.33.

F1, F2: core's own fixes arrive through the 0.3.33 range; as defence in depth a
served session refuses save_path, filepath and model_save_path anywhere in a
sub-tool's params or a workflow's config. F3: a plot export's name came from a
column name, unchecked. F4: loopback serve without a token checked neither Host
nor Origin. F5: served session folders were named with the session id, the
session's credential. F6: tool results echoed absolute paths containing it.
"""

import asyncio
import base64
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fastmcp import FastMCP
from starlette.testclient import TestClient

from stats_compass_mcp import exports, safety, tokens
from stats_compass_mcp.session import Session, SessionManager
from stats_compass_mcp.storage import LocalStorageBackend
from stats_compass_mcp.tools import register_all_tools

PNG = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * 16).decode()
SID = "f3a9c2e1d4b5a6978877665544332211"


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    out = {name: tmp_path / name for name in ("exports", "uploads", "elsewhere")}
    for path in out.values():
        path.mkdir()
    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", out["exports"])
    monkeypatch.setattr(exports, "UPLOADS_BASE_DIR", out["uploads"])
    monkeypatch.setattr(exports, "SERVER_URL", "https://example.test")
    monkeypatch.delenv("STATS_COMPASS_WRITE_ROOT", raising=False)
    monkeypatch.delenv("STATS_COMPASS_READ_ROOTS", raising=False)
    yield out
    safety.set_session_folder_namer(None)


def _server(dirs, *, confine=True):
    mcp = FastMCP("test")
    manager = SessionManager(confine_files=confine)
    storage = LocalStorageBackend(base_path=str(dirs["uploads"]))
    register_all_tools(mcp, manager, storage=storage)
    tools = asyncio.run(mcp._tool_manager.get_tools())
    session = manager.get_or_create(SID)
    session.state.set_dataframe(pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [0, 1, 0]}), "t", "test")
    return tools, session


def _call(tools, name, **kwargs):
    return tools[name].fn(ctx=SimpleNamespace(session_id=SID), **kwargs)


class TestServedSessionsRefuseWritePaths:
    @pytest.mark.parametrize(
        "tool, sub, params",
        [
            ("execute_plot_tool", "histogram", {"column": "x", "save_path": "/tmp/x.png"}),
            ("execute_ml_tool", "train_linear_regression", {"target_column": "x", "save_path": "m.joblib"}),
            ("execute_data_tool", "save_csv", {"dataframe_name": "t", "filepath": "/tmp/x.csv"}),
            ("execute_plot_tool", "histogram", {"column": "x", "nested": [{"model_save_path": "p"}]}),
        ],
    )
    def test_sub_tools(self, dirs, tool, sub, params):
        tools, _ = _server(dirs)
        with pytest.raises(ValueError, match="save"):
            _call(tools, tool, tool_name=sub, params=params)

    def test_workflow_config(self, dirs):
        tools, _ = _server(dirs)
        with pytest.raises(ValueError, match="save"):
            _call(tools, "run_classification_workflow", target_column="y",
                  config={"model_save_path": "/tmp/m.joblib"})

    def test_a_local_session_may_name_a_path(self, dirs):
        tools, _ = _server(dirs, confine=False)
        target = dirs["elsewhere"] / "h.png"
        _call(tools, "execute_plot_tool", tool_name="histogram",
              params={"dataframe_name": "t", "column": "x", "save_path": str(target)})
        assert target.exists()


class TestPlotExportNames:
    @pytest.mark.parametrize("prefix", ["/../../../../../../tmp/pwn", "eda_histogram_/../../../../x", "a\\b", ".."])
    def test_the_file_stays_in_the_sessions_plots(self, dirs, prefix):
        (exports.get_exports_dir(SID, "plots") / "eda_histogram_").mkdir(parents=True)  # the scan's pivot
        info = exports.save_plot_export(SID, PNG, prefix)
        written = Path(info["filepath"]).resolve()
        assert written.parent == exports.get_exports_dir(SID, "plots").resolve()
        assert "/" not in info["filename"] and ".." not in info["filename"]
        assert list(dirs["elsewhere"].iterdir()) == []

    def test_get_export_path_refuses_a_climbing_name(self, dirs):
        with pytest.raises(ValueError):
            exports.get_export_path(SID, "plots", "../../x.png")


class TestLoopbackHostAndOrigin:
    @pytest.fixture
    def client(self):
        from stats_compass_mcp.server import create_http_app

        with TestClient(create_http_app(auth_token=None), base_url="http://127.0.0.1:8000") as c:
            yield c

    def test_a_rebound_host_is_refused(self, client):
        assert client.post("/mcp", headers={"Host": "attacker.example"}, json={}).status_code == 403

    def test_a_foreign_origin_is_refused(self, client):
        assert client.post("/mcp", headers={"Origin": "http://attacker.example"}, json={}).status_code == 403

    @pytest.mark.parametrize("host", ["127.0.0.1:8000", "localhost:8000", "[::1]:8000", "localhost"])
    def test_loopback_hosts_pass(self, client, host):
        assert client.post("/mcp", headers={"Host": host, "Origin": f"http://{host}"}, json={}).status_code != 403

    def test_the_upload_page_on_localhost_works(self, client):
        assert client.get("/upload?token=x", headers={"Host": "localhost:8000"}).status_code == 200

    def test_a_token_or_a_public_bind_is_not_host_checked(self):
        from stats_compass_mcp.server import create_http_app

        for app in (create_http_app(auth_token="s3cret-token-value"), create_http_app(auth_token=None, host="0.0.0.0")):
            with TestClient(app, base_url="http://stats.example") as c:
                assert c.get("/upload?token=x").status_code == 200


class TestSessionFolders:
    def test_by_default_folders_keep_their_names(self, dirs):
        """Hosted names folders after its hashed user ids and reads them in its own routes."""
        assert Session(SID).state.file_policy.write_root == dirs["exports"] / SID

    def test_serve_names_them_by_hmac(self, dirs):
        safety.set_session_folder_namer(tokens.folder_name)
        folder = tokens.folder_name(SID)
        assert SID not in folder and len(folder) == 32
        state = Session(SID).state
        assert state.file_policy.write_root == dirs["exports"] / folder
        assert state.file_policy.read_roots == (dirs["uploads"] / folder,)
        assert exports.get_exports_dir(SID).name == folder
        assert LocalStorageBackend(base_path=str(dirs["uploads"]))._session_path(SID).name == folder

    def test_run_http_switches_it_on(self, dirs, monkeypatch):
        import uvicorn

        from stats_compass_mcp import server

        monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
        server.run_http(host="127.0.0.1")
        assert exports.get_exports_dir(SID).name == tokens.folder_name(SID)


class TestResultsCarryNamesNotPaths:
    def test_save_csv_and_save_model(self, dirs):
        tools, session = _server(dirs)
        csv = _call(tools, "save_csv", dataframe_name="t", filepath="out.csv")
        model_id = session.state.store_model({"w": 1}, "toy", "x", [], "t")
        model = _call(tools, "save_model", model_id=model_id, filepath="m.joblib")
        for result, name in ((csv, "out.csv"), (model, "m.joblib")):
            assert result["filepath"] == name
            assert SID not in str(result) and str(dirs["exports"]) not in str(result)
            assert result["download_url"]

    def test_load_csv_and_list_files(self, dirs):
        tools, _ = _server(dirs)
        (dirs["uploads"] / SID).mkdir()
        (dirs["uploads"] / SID / "orders.csv").write_text("a\n1\n")
        loaded = _call(tools, "load_csv", path="orders.csv")
        listed = _call(tools, "list_files")
        for result in (loaded, listed):
            assert SID not in str(result) and str(dirs["uploads"]) not in str(result)
        assert loaded["source"] == "orders.csv"
        assert listed["files"] == ["orders.csv"]

    def test_s3_upload_result_has_no_object_key(self, dirs, monkeypatch):
        pytest.importorskip("boto3")
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "test")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "test")
        from stats_compass_mcp.storage import S3StorageBackend

        safety.set_session_folder_namer(tokens.folder_name)
        result = S3StorageBackend(bucket="b", prefix="uploads", region="us-east-1").get_upload_url(SID, "x.csv")
        assert "object_key" not in result
        assert SID not in str(result)
