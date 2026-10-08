"""Upload and download links carry a signed, expiring token, not the session id.

stats-compass-mcp F2 (/download let '..' as the session id lift its own
containment base, exposing everything under /tmp), F4 (/api/upload wrote to a
caller-chosen session_id and file name, including absolute paths), F6 and F7
(download and upload URLs carried the raw session id, the session's only
credential). The token names the session, folder and file; the routes rebuild
the path from fixed folders and check it stays inside.
"""

import time

import pytest
from starlette.applications import Starlette
from starlette.testclient import TestClient

from stats_compass_mcp import exports, tokens, upload
from stats_compass_mcp.storage import LocalStorageBackend


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    out = {name: tmp_path / name for name in ("exports", "uploads")}
    for path in out.values():
        path.mkdir()
    (out["exports"] / "s1" / "data").mkdir(parents=True)
    (out["exports"] / "s1" / "data" / "report.csv").write_text("a\n1\n")
    (out["exports"] / "s2" / "data").mkdir(parents=True)
    (out["exports"] / "s2" / "data" / "theirs.csv").write_text("secret\n")
    (tmp_path / "debug.log").write_text("session s1 created\n")
    monkeypatch.setattr(exports, "EXPORTS_BASE_DIR", out["exports"])
    monkeypatch.setattr(exports, "UPLOADS_BASE_DIR", out["uploads"])
    monkeypatch.setattr(exports, "SERVER_URL", "https://example.test")
    return out


@pytest.fixture
def client(dirs):
    return TestClient(Starlette(routes=upload.create_upload_routes()))


class TestDownload:
    def test_a_signed_link_downloads_its_file(self, client):
        url = exports.get_download_url("s1", "data", "report.csv")
        assert "s1" not in url.split("/download/")[1].split(".")[-1]
        response = client.get(url.replace("https://example.test", ""))
        assert response.status_code == 200 and response.text == "a\n1\n"

    def test_the_session_id_is_not_in_the_link(self, dirs):
        assert "/s1/" not in exports.get_download_url("s1", "data", "report.csv")

    @pytest.mark.parametrize(
        "path",
        [
            "/download/%2e%2e/data/%2e%2e/debug.log",
            "/download/s1/data/report.csv",
            "/download/s2/data/theirs.csv",
            "/download/..%2f..%2fdebug.log",
        ],
    )
    def test_the_old_shapes_and_traversal_get_nothing(self, client, path):
        response = client.get(path)
        assert response.status_code in (403, 404)
        assert "secret" not in response.text and "created" not in response.text

    def test_a_tampered_token_is_refused(self, client):
        token = tokens.make_token("download", "s1", "data", "report.csv")
        payload, sig = token.split(".")
        forged = tokens.make_token("download", "s2", "data", "theirs.csv").split(".")[0] + "." + sig
        assert client.get(f"/download/{forged}").status_code == 403

    def test_an_expired_token_is_refused(self, client):
        token = tokens.make_token("download", "s1", "data", "report.csv", ttl=-1)
        assert client.get(f"/download/{token}").status_code == 403

    def test_an_upload_token_does_not_download(self, client):
        token = tokens.make_token("upload", "s1")
        assert client.get(f"/download/{token}").status_code == 403

    def test_a_signed_name_that_climbs_is_still_contained(self, client):
        token = tokens.make_token("download", "s1", "data", "../../s2/data/theirs.csv")
        response = client.get(f"/download/{token}")
        assert response.status_code in (403, 404) and "secret" not in response.text


class TestUpload:
    def _post(self, client, token, name="orders.csv", body=b"a\n1\n"):
        return client.post("/api/upload", data={"token": token}, files={"file": (name, body)})

    def test_the_upload_link_carries_a_token_not_the_session(self, dirs):
        backend = LocalStorageBackend(base_path=str(dirs["uploads"]), server_url="https://example.test")
        url = backend.get_upload_url("s1", "")["upload_url"]
        assert "token=" in url and "s1" not in url

    def test_a_valid_token_stores_the_file_in_its_session(self, client, dirs):
        assert self._post(client, tokens.make_token("upload", "s1")).status_code == 200
        assert (dirs["uploads"] / "s1" / "orders.csv").read_text() == "a\n1\n"

    @pytest.mark.parametrize("name", ["../../evil.csv", "/tmp/evil.csv", "..\\..\\evil.csv"])
    def test_the_file_name_is_reduced_to_a_base_name(self, client, dirs, name):
        assert self._post(client, tokens.make_token("upload", "s1"), name=name).status_code == 200
        stored = sorted(p.name for p in (dirs["uploads"] / "s1").iterdir())
        assert stored == ["evil.csv"]
        assert not (dirs["uploads"].parent / "evil.csv").exists()

    def test_a_session_id_in_the_form_is_not_a_credential(self, client, dirs):
        response = client.post(
            "/api/upload",
            data={"session_id": str(dirs["exports"] / "s2" / "data")},
            files={"file": ("planted.csv", b"x\n")},
        )
        assert response.status_code in (400, 403)
        assert not (dirs["exports"] / "s2" / "data" / "planted.csv").exists()

    @pytest.mark.parametrize("token", ["", "nonsense", "a.b"])
    def test_a_bad_token_is_refused(self, client, token):
        assert self._post(client, token).status_code in (400, 403)

    def test_a_download_token_does_not_upload(self, client):
        token = tokens.make_token("download", "s1", "data", "report.csv")
        assert self._post(client, token).status_code == 403

    def test_only_data_files(self, client):
        assert self._post(client, tokens.make_token("upload", "s1"), name="x.py").status_code == 400

    def test_the_page_does_not_show_a_session_id(self, client):
        page = client.get("/upload?token=abc").text
        assert "Session ID" not in page and "session_id" not in page


def test_tokens_expire_when_asked():
    token = tokens.make_token("upload", "s1", ttl=1)
    assert tokens.read_token(token, "upload")["session_id"] == "s1"
    time.sleep(1.1)
    assert tokens.read_token(token, "upload") is None
