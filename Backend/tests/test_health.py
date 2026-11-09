"""Boot resilience.

The failure this exists for: `create_all()` used to run at module import, so
an unreachable database raised during import, uvicorn never built an `app`
object, and the only symptom was a bare 502. No health endpoint, no log past
the traceback, and no way to tell a database outage from a crashed container
or a broken proxy — on a host where redeploying reinstalls every dependency.
"""
from __future__ import annotations

from app import main as app_main

KEY = {"X-Export-Key": "test-export-key"}


def test_health_reports_a_reachable_database(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["app"] == "up"
    assert body["database"]["reachable"] is True
    assert body["database"]["error"] is None


def test_health_never_leaks_the_database_password():
    """The endpoint is deliberately NOT key-gated, so it must be safe to hit
    from anywhere — which means the connection string cannot go out whole."""
    from app import config

    original = config.DATABASE_URL
    try:
        config.DATABASE_URL = (
            "postgresql+psycopg://appuser:sup3rs3cret@10.0.0.5:5432/moirai")
        redacted = app_main._redacted_db_url()
        assert "sup3rs3cret" not in redacted
        assert "appuser" in redacted   # identity is useful, secret is not
        assert "10.0.0.5:5432" in redacted
    finally:
        config.DATABASE_URL = original


def test_redaction_leaves_a_sqlite_path_alone():
    from app import config

    original = config.DATABASE_URL
    try:
        config.DATABASE_URL = "sqlite:////data/app.db"
        assert app_main._redacted_db_url() == "sqlite:////data/app.db"
    finally:
        config.DATABASE_URL = original


def test_init_db_requires_the_export_key(client):
    """It writes schema, so it cannot be open."""
    assert client.post("/api/health/init-db").status_code == 403
    assert client.post("/api/health/init-db",
                       headers={"X-Export-Key": "wrong"}).status_code == 403


def test_init_db_succeeds_with_the_key(client):
    r = client.post("/api/health/init-db", headers=KEY)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "error": None}


def test_init_database_reports_failure_instead_of_raising(monkeypatch):
    """The whole point: a database error must become a RETURN VALUE, not an
    exception that kills the process before it can serve anything."""
    def boom(*a, **k):
        raise RuntimeError("connection failed: server closed the connection")

    monkeypatch.setattr(app_main.Base.metadata, "create_all", boom)
    err = app_main.init_database()
    assert err is not None
    assert "connection failed" in err


def test_init_database_can_still_raise_when_asked(monkeypatch):
    """Kept for callers that genuinely want fail-fast, e.g. a migration
    script where continuing past a failure would be worse."""
    import pytest

    def boom(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(app_main.Base.metadata, "create_all", boom)
    with pytest.raises(RuntimeError):
        app_main.init_database(raise_on_failure=True)


def test_stale_schema_self_heals_on_the_next_request(client, monkeypatch):
    """A database that was down at boot and came back must not leave the app
    running against a schema that was never migrated.

    That state is the worst kind: the app looks healthy, but every query
    touching a newly-added column fails with UndefinedColumn, and the
    participant simply loops with nothing in the UI to explain it.
    """
    app_main.DB_INIT_ERROR = "OperationalError: server closed the connection"
    app_main._LAST_INIT_RETRY = 0.0

    r = client.get("/api/health")
    assert r.status_code == 200
    # The retry ran during the request and cleared the flag.
    assert app_main.DB_INIT_ERROR is None


def test_retry_is_throttled_while_the_database_stays_down(client, monkeypatch):
    """A long outage must not mean a fresh connection attempt on every single
    request — that turns a slow database into a much slower one."""
    calls = []

    def failing_init(**kwargs):
        calls.append(1)
        return "still down"

    monkeypatch.setattr(app_main, "init_database", failing_init)
    app_main.DB_INIT_ERROR = "down"
    app_main._LAST_INIT_RETRY = 0.0

    for _ in range(5):
        client.get("/api/health")

    assert len(calls) == 1, "retry should be throttled, not per-request"
    app_main.DB_INIT_ERROR = None
