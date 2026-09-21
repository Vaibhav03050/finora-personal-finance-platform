"""Tests for security hardening added during the final audit:
- upload size limits (memory-exhaustion prevention)
- refusal to start in production with the default insecure JWT secret
"""
import subprocess
import sys


def test_csv_upload_over_size_limit_rejected(client, auth_headers):
    oversized_content = b"Date,Description,Amount\n" + (b"01/01/2026,Test,100\n" * 700000)  # ~14MB, comfortably over 10MB
    assert len(oversized_content) > 10 * 1024 * 1024
    resp = client.post(
        "/api/v1/transactions/upload-csv",
        headers=auth_headers,
        files={"file": ("big.csv", oversized_content, "text/csv")},
    )
    assert resp.status_code == 413


def test_csv_upload_under_size_limit_accepted(client, auth_headers):
    small_content = b"Date,Description,Amount\n01/01/2026,Test,100\n"
    resp = client.post(
        "/api/v1/transactions/upload-csv",
        headers=auth_headers,
        files={"file": ("small.csv", small_content, "text/csv")},
    )
    assert resp.status_code == 200


def test_statement_photo_over_size_limit_rejected(client, auth_headers):
    oversized_content = b"\x00" * (11 * 1024 * 1024)
    resp = client.post(
        "/api/v1/uploads/statement-photo",
        headers=auth_headers,
        files={"file": ("big.png", oversized_content, "image/png")},
    )
    assert resp.status_code == 413


def test_receipt_photo_over_size_limit_rejected(client, auth_headers):
    oversized_content = b"\x00" * (11 * 1024 * 1024)
    resp = client.post(
        "/api/v1/uploads/receipt-photo",
        headers=auth_headers,
        files={"file": ("big.png", oversized_content, "image/png")},
    )
    assert resp.status_code == 413


def test_app_refuses_to_start_in_production_with_default_jwt_secret():
    """Runs a fresh subprocess importing app.config with ENV=production and
    the default secret still set, to confirm the startup guard fires -
    can't test this in-process since settings are already loaded."""
    import os
    env = os.environ.copy()
    env["ENV"] = "production"
    env.pop("FIN_JWT_SECRET", None)  # ensure it falls back to the insecure default
    env["DATABASE_URL"] = "sqlite:///:memory:"

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import settings"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "placeholder" in result.stderr.lower() or "placeholder" in result.stdout.lower()


def test_app_refuses_to_start_in_production_with_env_example_placeholder():
    """Regression test: .env.example ships its own placeholder wording
    ('change-me-to-a-long-random-string-in-production'), different from the
    Python-level default. A user who follows the README's own 'cp
    .env.example .env' instruction and deploys as-is must still be caught -
    this previously slipped through when the guard only checked one exact
    string."""
    import os
    env = os.environ.copy()
    env["ENV"] = "production"
    env["FIN_JWT_SECRET"] = "change-me-to-a-long-random-string-in-production"
    env["DATABASE_URL"] = "sqlite:///:memory:"

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import settings"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode != 0
    assert "placeholder" in result.stderr.lower() or "placeholder" in result.stdout.lower()


def test_app_starts_fine_in_production_with_real_secret_set():
    import os
    env = os.environ.copy()
    env["ENV"] = "production"
    env["FIN_JWT_SECRET"] = "a-real-randomly-generated-production-secret"
    env["DATABASE_URL"] = "sqlite:///:memory:"

    result = subprocess.run(
        [sys.executable, "-c", "from app.config import settings; print('OK')"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout
