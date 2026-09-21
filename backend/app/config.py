"""
Central configuration. Every secret / tunable comes from environment
variables so nothing sensitive is hardcoded in source.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Core ---
    APP_NAME: str = "Finora"
    ENV: str = "development"

    # --- Database ---
    # SQLite by default (zero setup). Swap for a Mongo/Postgres URL in prod
    # without touching the service layer, which never talks to the DB directly.
    DATABASE_URL: str = "sqlite:///./finora.db"

    # --- Auth ---
    FIN_JWT_SECRET: str = "dev-only-secret-change-me-in-production"
    FIN_JWT_ALGORITHM: str = "HS256"
    FIN_JWT_EXPIRE_MINUTES: int = 30

    # --- AI Provider ---
    # If FIN_AI_API_KEY is empty, the app runs entirely on deterministic
    # template-based explanations. No feature requires an API key.
    FIN_AI_PROVIDER: str = "none"          # "openai" | "none"
    FIN_AI_API_KEY: str = ""
    FIN_AI_BASE_URL: str = "https://api.openai.com/v1"
    FIN_AI_MODEL: str = "gpt-4o-mini"

    # --- OCR ---
    FIN_OCR_ENGINE: str = "tesseract"

    # --- CORS ---
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"


settings = Settings()

# Refuse to boot in production with an unchanged placeholder JWT secret.
# Checks for a "change me"-style marker rather than one exact string, since
# .env.example ships its own differently-worded placeholder
# ("change-me-to-a-long-random-string-in-production") that must be caught
# too, not just the bare Python-level default.
_PLACEHOLDER_MARKERS = ("change-me", "change_me", "changeme", "dev-only-secret")
if settings.ENV == "production" and any(marker in settings.FIN_JWT_SECRET.lower() for marker in _PLACEHOLDER_MARKERS):
    raise RuntimeError(
        "Refusing to start with ENV=production while FIN_JWT_SECRET still looks like "
        "an unchanged placeholder. Set a real, random FIN_JWT_SECRET environment "
        "variable before deploying to production."
    )
