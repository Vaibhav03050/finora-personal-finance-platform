"""Tests for CORS configuration. The app is configured with a fixed
CORS_ORIGINS allowlist (default: http://localhost:8000, http://127.0.0.1:8000)
and allow_credentials=True, which means wildcard origins must never be used
(invalid per the CORS spec, and a security foot-gun if it were)."""


def test_preflight_from_allowed_origin_succeeds(client):
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert resp.headers["access-control-allow-credentials"] == "true"
    assert "POST" in resp.headers["access-control-allow-methods"]


def test_preflight_from_disallowed_origin_rejected(client):
    resp = client.options(
        "/api/v1/auth/login",
        headers={
            "Origin": "http://evil.example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )
    assert resp.status_code == 400
    assert "access-control-allow-origin" not in resp.headers


def test_actual_request_from_allowed_origin_gets_cors_headers(client):
    resp = client.get("/healthz", headers={"Origin": "http://localhost:8000"})
    assert resp.status_code == 200
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8000"
    assert resp.headers["access-control-allow-credentials"] == "true"


def test_actual_request_from_disallowed_origin_gets_no_cors_header(client):
    """The server still answers (CORS is a browser-enforced policy, not a
    server-side firewall) but omits the ACAO header, so a real browser's JS
    would be blocked from reading the response even though this test client
    can see the body."""
    resp = client.get("/healthz", headers={"Origin": "http://evil.example.com"})
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_actual_request_with_no_origin_header_has_no_cors_headers(client):
    """Server-to-server / non-browser clients (curl, other services) don't
    send Origin, so no CORS headers are added - this is correct, not a gap."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert "access-control-allow-origin" not in resp.headers


def test_both_default_allowed_origins_work(client):
    for origin in ["http://localhost:8000", "http://127.0.0.1:8000"]:
        resp = client.get("/healthz", headers={"Origin": origin})
        assert resp.headers["access-control-allow-origin"] == origin


def test_cors_never_uses_wildcard_origin_when_credentials_allowed(client):
    """Security regression check: allow_credentials=True + wildcard origin
    is invalid per the CORS spec and would be a real vulnerability if
    misconfigured. The response must always echo the exact origin, never '*'."""
    resp = client.get("/healthz", headers={"Origin": "http://localhost:8000"})
    assert resp.headers["access-control-allow-origin"] != "*"
    assert resp.headers["access-control-allow-origin"] == "http://localhost:8000"
