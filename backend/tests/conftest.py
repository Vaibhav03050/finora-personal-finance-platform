import os
import sys
from pathlib import Path

# Point at an isolated test DB before importing the app.
TEST_DB_PATH = Path(__file__).parent / "test_finora.db"
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"
# Rate limiting is bypassed in the test environment: a full test-suite run
# fires hundreds of HTTP requests in seconds from the same TestClient "IP",
# which would otherwise trip the 120-req/60s production limit and cause
# unrelated tests to fail with 429s. Production rate limiting is untouched.
os.environ["ENV"] = "test"

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="session", autouse=True)
def clean_db():
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()


@pytest.fixture()
def client():
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def auth_headers(client):
    email = "test_user_1@example.com"
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Test User"})
    if resp.status_code == 409:
        resp = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    token = resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def admin_headers(client):
    """Registers a fresh user and promotes them to admin directly via the DB
    (there is no API endpoint for this by design - admin accounts are
    provisioned out-of-band), then re-authenticates so the issued JWT
    carries role=admin."""
    import uuid
    from sqlmodel import Session, select
    from app.database import engine
    from app.models import User

    email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": "password123", "name": "Admin"})
    assert resp.status_code == 200

    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == email)).first()
        user.role = "admin"
        session.add(user)
        session.commit()

    login_resp = client.post("/api/v1/auth/login", json={"email": email, "password": "password123"})
    token = login_resp.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}
