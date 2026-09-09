from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import (
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
from fastapi.staticfiles import StaticFiles
from pathlib import Path
# Ensure tables exist in dev, then patch in any column added since the
# database was first created (create_all does not alter existing tables).
Base.metadata.create_all(bind=engine)
ensure_columns()

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
app.include_router(extension.router)
app.include_router(auth.router)
app.include_router(eft.router)
app.include_router(events.router)
app.include_router(participant_router)
app.include_router(study_router)
app.include_router(research_router)
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
