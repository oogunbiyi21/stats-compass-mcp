"""`serve` is local unless it has a token (security scan, 8 Oct 2026, F3).

It used to bind 0.0.0.0 with no authentication, so anyone who could reach the
port could use every tool. It now binds 127.0.0.1 by default; a non-loopback
address needs a bearer token (STATS_COMPASS_AUTH_TOKEN or --auth-token), or an
explicit --no-auth that logs a warning. The upload and download routes are not
behind the bearer token: their signed link is their credential.
"""

import logging

import pytest
from starlette.testclient import TestClient

from stats_compass_mcp.cli import build_parser
from stats_compass_mcp.server import check_bind, create_http_app


def test_serve_binds_loopback_by_default():
    args = build_parser().parse_args(["serve"])
    assert args.host == "127.0.0.1"


class TestBindPolicy:
    @pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.2"])
    def test_loopback_needs_no_token(self, host):
        check_bind(host, auth_token=None, allow_no_auth=False)

    @pytest.mark.parametrize("host", ["0.0.0.0", "::", "192.168.1.5", "example.com"])
    def test_a_public_bind_without_a_token_is_refused(self, host):
        with pytest.raises(SystemExit):
            check_bind(host, auth_token=None, allow_no_auth=False)

    def test_a_public_bind_with_a_token_is_allowed(self):
        check_bind("0.0.0.0", auth_token="s3cret-token-value", allow_no_auth=False)

    def test_no_auth_is_allowed_but_loud(self, caplog):
        with caplog.at_level(logging.WARNING):
            check_bind("0.0.0.0", auth_token=None, allow_no_auth=True)
        assert any("without authentication" in r.message for r in caplog.records)

    def test_a_short_token_is_refused(self):
        with pytest.raises(SystemExit):
            check_bind("0.0.0.0", auth_token="abc", allow_no_auth=False)


class TestBearerToken:
    @pytest.fixture
    def client(self):
        with TestClient(create_http_app(auth_token="s3cret-token-value")) as c:
            yield c

    @pytest.mark.parametrize("header", [None, "Bearer wrong", "s3cret-token-value", "Basic s3cret-token-value"])
    def test_mcp_without_the_token_is_401(self, client, header):
        headers = {"Authorization": header} if header else {}
        assert client.post("/mcp", headers=headers, json={}).status_code == 401

    def test_mcp_with_the_token_gets_through(self, client):
        response = client.post(
            "/mcp", headers={"Authorization": "Bearer s3cret-token-value"}, json={}
        )
        assert response.status_code != 401

    def test_the_upload_page_and_routes_are_not_behind_it(self, client):
        assert client.get("/upload?token=x").status_code == 200
        assert client.post("/api/upload", data={"token": "x"}).status_code == 403
        assert client.get("/download/x").status_code == 403

    def test_no_token_means_no_check(self):
        with TestClient(create_http_app(auth_token=None)) as c:
            assert c.post("/mcp", json={}).status_code != 401
