import time

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.config import (
    ADMIN_EXPORT_KEY,
    APP_NAME,
    BUNDLED_STATIC_DIR,
    CORS_ORIGINS,
    REMINDERS_DIR,
    describe_llm,
    describe_storage,
)
from app.database.db_setup import Base, engine, ensure_columns
from app.routers import auth, eft, events, extension, measures
from app.routers.participant import router as participant_router
from app.routers.study import router as study_router
from app.routers.research import router as research_router
from app.routers.cues import router as cues_router
from fastapi.staticfiles import StaticFiles
from pathlib import Path
def init_database(*, raise_on_failure: bool = False) -> str | None:
    """Create missing tables, then patch in columns added since.

    Returns None on success, or the error string.

    DELIBERATELY NOT CALLED AT IMPORT TIME. It used to be, and that turned
    every database hiccup into a total outage: the import raised, uvicorn
    never produced an `app` object, and the only symptom was a bare 502 with
    no application log — no health endpoint, no error page, nothing to say
    whether the problem was the database, the code or the proxy.

    Now the app boots regardless and says what is wrong. Requests that need
    the database still fail, loudly and individually, which is strictly more
    information than the process being gone.
    """
    try:
        Base.metadata.create_all(bind=engine)
        ensure_columns()
        return None
    except Exception as e:
        detail = f"{type(e).__name__}: {e}"
        if raise_on_failure:
            raise
        print("=" * 72)
        print("⚠️  DATABASE UNREACHABLE AT STARTUP — the app is running but "
              "cannot serve any request that touches the database.")
        print(f"    {detail}")
        print(f"    url: {_redacted_db_url()}")
        print("    Tables have NOT been created or migrated. Check "
              "GET /api/health, fix the database, then redeploy or call "
              "POST /api/health/init-db to retry without a redeploy.")
        print("=" * 72)
        return detail


def _redacted_db_url() -> str:
    """The database URL with the password removed, safe to print or serve."""
    from app.config import DATABASE_URL
    url = DATABASE_URL
    if "@" in url and "//" in url:
        head, tail = url.split("//", 1)
        creds, host = tail.split("@", 1)
        user = creds.split(":", 1)[0]
        return f"{head}//{user}:***@{host}"
    return url


# Attempted at startup. A failure is recorded, not raised.
DB_INIT_ERROR: str | None = init_database()

# When startup init failed, retry it on incoming requests — throttled, so a
# long outage does not mean a connection attempt per request.
#
# Without this, a database that was down at boot and came back leaves the app
# running against a STALE SCHEMA: it serves fine, but every query touching a
# column added in this release fails with UndefinedColumn, and the only way
# out is a manual call or a redeploy. That is a silent, confusing failure —
# the app looks healthy and the participant just loops.
_LAST_INIT_RETRY = 0.0
_INIT_RETRY_INTERVAL_SECONDS = 30.0

# Generated reminder images live under DATA_DIR (the persistent disk on the
# server — see config.py); everything else under /static ships with the code.
REMINDERS_DIR.mkdir(parents=True, exist_ok=True)
BUNDLED_STATIC_DIR.mkdir(parents=True, exist_ok=True)

# The Flutter web build, copied here by scripts/build_web.sh. Absent during
# backend-only development, in which case the app just serves the API.
WEB_DIR = Path(__file__).resolve().parent / "web"

app = FastAPI(title=APP_NAME)

# Which provider/models this process will actually use. Printed at boot
# because every LLM failure mode here is silent by design (canned questions,
# no image) — without this you find out from the behaviour, not the logs.
print(f"🧠 {describe_llm()}")
print(f"💾 {describe_storage()}")

# 🔹 CORS — empty by default. The Flutter build is served from this same
# origin, so no cross-origin grant is needed; set CORS_ORIGINS only when the
# frontend is hosted separately.
if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


# 🔹 Liveness probe for the host's healthcheck (and for the desktop launcher,
# which polls this before showing the UI).
@app.get("/health")
def health():
    return {"status": "ok"}


# 🔹 APIs live under /api/...
@app.middleware("http")
async def _retry_db_init_if_needed(request, call_next):
    """Re-attempt schema setup if it failed at startup. No-op once it works."""
    global DB_INIT_ERROR, _LAST_INIT_RETRY
    if DB_INIT_ERROR is not None:
        now = time.monotonic()
        if now - _LAST_INIT_RETRY > _INIT_RETRY_INTERVAL_SECONDS:
            _LAST_INIT_RETRY = now
            DB_INIT_ERROR = init_database()
            if DB_INIT_ERROR is None:
                print("✅ database reachable again — schema created/migrated.")
    return await call_next(request)


@app.get("/api/health")
def health():
    """Is the app up, and can it actually reach its database?

    Exists because the previous failure mode was a bare 502 with no running
    process: nothing to ask, nothing logged past the traceback, and no way to
    tell a database outage from a crashed container or a proxy fault. This
    answers that question in one request, without the export key, and without
    revealing the database password.
    """
    from sqlalchemy import text

    db_ok, db_error = False, None
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception as e:
        db_error = f"{type(e).__name__}: {e}"

    return {
        "app": "up",
        "database": {
            "reachable": db_ok,
            "url": _redacted_db_url(),
            "error": db_error,
            # Set if table creation failed when the process started. A
            # reachable database with this still set means the schema was
            # never built — call the init endpoint below.
            "startup_init_error": DB_INIT_ERROR,
        },
    }


@app.post("/api/health/init-db")
def init_db_now(x_export_key: str | None = Header(default=None)):
    """Retry table creation, for when the database came back after boot.

    Without this, recovering from a startup outage needs a redeploy — which
    on this host means a full reinstall of every dependency, so a 30-second
    database blip costs several minutes and a rebuild.

    Key-gated: it writes schema.
    """
    if not x_export_key or x_export_key != ADMIN_EXPORT_KEY:
        raise HTTPException(status_code=403,
                            detail="Invalid or missing X-Export-Key header")
    global DB_INIT_ERROR
    DB_INIT_ERROR = init_database()
    return {"ok": DB_INIT_ERROR is None, "error": DB_INIT_ERROR}


app.include_router(extension.router)
app.include_router(auth.router)
app.include_router(eft.router)
app.include_router(events.router)
app.include_router(participant_router)
app.include_router(study_router)
app.include_router(research_router)
app.include_router(cues_router)
app.include_router(measures.router)

# 🔹 Generated reminder images. Mounted BEFORE /static so the writable disk
# wins for this subpath — the URLs stay /static/reminders/... either way.
app.mount(
    "/static/reminders",
    StaticFiles(directory=str(REMINDERS_DIR)),
    name="reminders",
)
app.mount("/static", StaticFiles(directory=str(BUNDLED_STATIC_DIR)), name="static")

# 🔹 Serve the Flutter build at ROOT. Must stay last: a mount at "/" matches
# everything, so any route declared after it would be unreachable.
if WEB_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")
