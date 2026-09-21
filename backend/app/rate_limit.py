"""Lightweight in-memory rate limiter (per-IP sliding window). Good enough
for a single-instance deployment; swap for Redis in a multi-instance setup."""
import time
from collections import defaultdict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings

WINDOW_SECONDS = 60
MAX_REQUESTS = 120

# Infra/health-check endpoints are never rate limited - load balancers and
# orchestrators (e.g. Kubernetes liveness probes) poll these frequently from
# shared IPs, and blocking them could cause false-negative health checks.
EXEMPT_PATHS = {"/healthz", "/readyz", "/metrics"}

# Browser page loads can request several static assets in quick succession.
# These resources are not API mutations and should never consume the API
# request budget. This also prevents repeated local refreshes from locking
# the SPA behind a 429 response.
def _is_exempt_request(request: Request) -> bool:
    path = request.url.path
    if path in EXEMPT_PATHS or path.startswith("/static/"):
        return True
    # The SPA shell and favicon are safe GET resources. Keep API routes
    # (including uploads) subject to the limiter.
    return request.method == "GET" and path in {"/", "/favicon.ico"}

_hits: dict[str, list[float]] = defaultdict(list)


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_exempt_request(request) or settings.ENV == "test":
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - WINDOW_SECONDS

        recent = [t for t in _hits[client_ip] if t > window_start]
        recent.append(now)
        _hits[client_ip] = recent

        if len(recent) > MAX_REQUESTS:
            return JSONResponse(
                status_code=429,
                content={"success": False, "data": None, "error": {"code": "RATE_LIMITED", "message": "Too many requests, please slow down.", "details": {}}, "meta": {}},
            )
        return await call_next(request)
