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
