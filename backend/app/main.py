import logging
from pathlib import Path

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.database import init_db
from app.rate_limit import RateLimitMiddleware
from app.routers import admin, analytics, assistant, auth, education, goals, profile, simulator, transactions, uploads
from app.schemas import fail

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("finora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Finora backend started. AI provider: %s", settings.FIN_AI_PROVIDER)
    yield


app = FastAPI(
    title="Finora API",
    description="AI-Powered Personal Finance & Goal Planning Platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Never leak stack traces / internals - consistent error envelope everywhere.
    return JSONResponse(status_code=exc.status_code, content=fail("HTTP_ERROR", str(exc.detail)))


# --- Routers ---
app.include_router(auth.router)
app.include_router(transactions.router)
app.include_router(uploads.router)
app.include_router(goals.router)
app.include_router(analytics.router)
app.include_router(profile.router)
app.include_router(assistant.router)
app.include_router(education.router)
app.include_router(simulator.router)
app.include_router(admin.router)


# --- Ops endpoints ---
@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/readyz")
def readyz():
    return {"status": "ready"}


@app.get("/metrics")
def metrics():
    # Minimal placeholder metrics endpoint (Prometheus-format text can be
    # wired in later without changing this contract).
    return {"status": "ok", "note": "metrics collection not wired to an external system in this build"}


# --- Serve the frontend (static SPA-style app) ---
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        index_file = FRONTEND_DIR / "templates" / "index.html"
        return FileResponse(index_file)
