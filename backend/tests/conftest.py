import os
import sys
from pathlib import Path

import pytest

# Make `app` importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Use a temp DB per test session and avoid reading the user's .env
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_banxico.db")
os.environ["PROVIDER"] = "anthropic"
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")


@pytest.fixture()
def db_session(tmp_path, monkeypatch):
    db_file = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")

    # Reload modules that captured settings at import time
    for mod in [
        "app.config",
        "app.db",
        "app.models",
        "app.personas",
    ]:
        sys.modules.pop(mod, None)

    from app.db import SessionLocal, init_db  # noqa: WPS433

    init_db()
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def test_user(db_session):
    from app.auth import hash_password
    from app.models import User

    user = User(username="tester", display_name="Tester", password_hash=hash_password("secret123"))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    db_file = tmp_path / "test_api.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_file}")
    monkeypatch.setenv("JWT_SECRET", "test-secret-not-for-production")

    for mod in [
        "app.config",
        "app.db",
        "app.models",
        "app.personas",
        "app.auth",
        "app.routes.auth",
        "app.routes.chat",
        "app.routes.meeting",
        "app.routes.agents",
        "app.main",
    ]:
        sys.modules.pop(mod, None)

    from app.main import app

    return TestClient(app)


@pytest.fixture()
def auth_headers(client):
    res = client.post(
        "/api/auth/register",
        json={"username": "tester", "display_name": "Tester", "password": "secret123"},
    )
    assert res.status_code == 201, res.text
    token = res.json()["token"]
    return {"Authorization": f"Bearer {token}"}
