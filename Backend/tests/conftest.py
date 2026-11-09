"""Test harness: a real FastAPI app against a throwaway in-memory database.

Auth is overridden rather than exercised — these tests are about the cue
protocol, and driving real signup/login through every test would test the
login route over and over instead.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Import app.config with test-safe settings BEFORE anything else pulls it in:
# it reads the environment at import time and refuses to boot without secrets.
os.environ.setdefault("DEBUG_MODE", "True")
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("ADMIN_EXPORT_KEY", "test-export-key")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.database import models  # noqa: E402
from app.database.db_setup import Base, SessionLocal, engine  # noqa: E402
from app.database.db_setup import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.security import get_current_user  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def make_user(db):
    def _make(study_group: str = "eft", code: str = "P001") -> models.User:
        user = models.User(participant_code=code, password_hash="x",
                           study_group=study_group)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    return _make


@pytest.fixture()
def client(db):
    """A client whose identity can be swapped with `client.login(user)`."""
    state = {"user": None}

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: state["user"]

    c = TestClient(app)
    c.login = lambda user: state.__setitem__("user", user)
    try:
        yield c
    finally:
        app.dependency_overrides.clear()


@pytest.fixture()
def session_for(db):
    def _make(user: models.User) -> models.Session:
        s = models.Session(user_id=user.id, session_number=1)
        db.add(s)
        db.commit()
        db.refresh(s)
        return s
    return _make


@pytest.fixture()
def assets_for(db):
    """Two personalized reminder assets, matching the two cue slots."""
    def _make(user: models.User, count: int = 2):
        for i in range(count):
            db.add(models.ReminderAsset(
                user_id=user.id, asset_index=i,
                image_url=f"/static/reminders/u{user.id}_{i}.png",
                cue=f"cue {i}", is_generic=False))
        db.commit()
    return _make
