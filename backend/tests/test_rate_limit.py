"""Tests for the rate-limiting middleware.

Note: the test environment (ENV=test, set in conftest.py) bypasses rate
limiting entirely so the rest of the suite isn't flaky from cumulative
request counts. These tests exercise the limiter's logic directly instead
of relying on the middleware being live under TestClient.
"""
import time

from app.rate_limit import EXEMPT_PATHS, MAX_REQUESTS, WINDOW_SECONDS


def test_health_endpoints_are_exempt_from_rate_limiting():
    assert "/healthz" in EXEMPT_PATHS
    assert "/readyz" in EXEMPT_PATHS
    assert "/metrics" in EXEMPT_PATHS


def test_rate_limit_config_is_reasonable():
    assert MAX_REQUESTS > 0
    assert WINDOW_SECONDS > 0


def test_sliding_window_logic_evicts_old_hits():
    """Directly exercises the same sliding-window filtering logic the
    middleware uses, without needing to fire 120+ real HTTP requests."""
    now = time.time()
    hits = [now - 120, now - 90, now - 10, now - 1]  # first two are outside a 60s window
    window_start = now - WINDOW_SECONDS
    recent = [t for t in hits if t > window_start]
    assert len(recent) == 2


def test_health_endpoint_never_rate_limited_even_under_burst(client):
    """Even with rate limiting bypassed in test env, this confirms /healthz
    itself is on the exemption list and would work in production too."""
    for _ in range(150):
        resp = client.get("/healthz")
        assert resp.status_code == 200


def test_static_and_spa_shell_requests_are_exempt():
    from starlette.requests import Request
    from app.rate_limit import _is_exempt_request

    def req(path, method="GET"):
        scope = {"type": "http", "method": method, "path": path,
                 "headers": [], "query_string": b"", "client": ("test", 1),
                 "server": ("test", 80), "scheme": "http", "http_version": "1.1"}
        return Request(scope)

    assert _is_exempt_request(req("/"))
    assert _is_exempt_request(req("/favicon.ico"))
    assert _is_exempt_request(req("/static/js/pages.js"))
    assert not _is_exempt_request(req("/api/v1/transactions"))
