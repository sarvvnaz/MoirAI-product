from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import timedelta

# ─────────────────────────────
# ENVIRONMENT SETUP
# ─────────────────────────────

# Locate the Backend folder (parent of /app)
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables from .env in /Backend
load_dotenv(ENV_PATH)

# ─────────────────────────────
# CORE SETTINGS
# ─────────────────────────────

# True in local development, False on the deployed server. Several settings
# below refuse to fall back to a dev default once this is off, so the server
# fails loudly at boot rather than running with a guessable secret.
DEBUG_MODE = os.getenv("DEBUG_MODE", "True").lower() == "true"

# Everything the app WRITES at runtime lives here: the SQLite file and the
# generated reminder images. Locally that stays inside the repo; on the
# server point DATA_DIR at the mounted persistent disk (e.g. /data), because
# a container's own filesystem is wiped on every redeploy and this directory
# holds participant data.
DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "static")).resolve()

# Generated reminder images. Served at /static/reminders/... — keep that URL
# stable, it is stored in the database and fetched by the extension.
REMINDERS_DIR = DATA_DIR / "reminders"

# Read-only assets shipped with the code (placeholder image, extension zip).
BUNDLED_STATIC_DIR = BASE_DIR / "static"

DB_PATH = BASE_DIR / "database" / "app.db"

# Absolute by default, so the SQLite file is found no matter which directory
# uvicorn was started from. On the server set DATABASE_URL explicitly — to
# Postgres, or to a SQLite path on the persistent disk:
#     postgresql+psycopg://user:pass@host:5432/dbname
#     sqlite:////data/app.db          (four slashes = absolute path)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")

# Hosting panels hand out "postgresql://..." (or the older "postgres://").
# SQLAlchemy reads both as psycopg2, which is not installed — the driver here
# is psycopg 3 — so a correctly copied URL would fail at boot with an obscure
# ModuleNotFoundError about psycopg2. Normalise instead of making that
# someone's problem at 2am.
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg://" + DATABASE_URL[len("postgresql://"):]

# That fallback writes INSIDE the deployed code directory, which a container
# rebuilds on every deploy. In development that is exactly right; in
# production it is silent, total data loss that looks like "the database keeps
# resetting" with nothing in the log to explain it.
#
# So a deployed server must say where its database lives. If DATABASE_URL
# fails to reach the process for any reason, refuse to start rather than
# quietly collect participants into a file that is about to be deleted.
if not DEBUG_MODE and not os.getenv("DATABASE_URL"):
    raise RuntimeError(
        "DATABASE_URL is not set. With DEBUG_MODE off the database must be "
        "given an explicit location on persistent storage — otherwise it "
        f"defaults to {DB_PATH}, inside the code directory, and every "
        "redeploy destroys all participant data.\n"
        "    Set e.g. DATABASE_URL=sqlite:////data/app.db  (four slashes)\n"
        "    or a managed Postgres URL."
    )

# Origins allowed to call the API cross-origin. Empty by default: the Flutter
# build is served from this same server, so same-origin requests need no CORS
# grant at all. Only set this if you host the frontend somewhere else.
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]

# ─────────────────────────────
# LLM PROVIDER + MODELS
# ─────────────────────────────
# Every model the app uses is named HERE and nowhere else, so switching
# provider or model is a .env change rather than a hunt through the code.
# (A missed model name fails silently into a fallback — the chatbot serves
# canned questions, images never generate — so keep this the single source.)

# Which provider to talk to. 'avalai' is the OpenAI-compatible gateway used
# for access from Iran; 'openai' talks to OpenAI directly (useful for
# debugging, or when the gateway is out of credit).
#
# The key and the endpoint are chosen TOGETHER on purpose. Picking them
# independently is a trap: AVALAI_API_KEY used to win unconditionally, so
# adding an OPENAI_API_KEY and repointing the base URL would quietly send the
# gateway's key to OpenAI and fail with a confusing 401.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "avalai").strip().lower()

# Images can use a DIFFERENT provider from chat. They have different
# constraints: chat needs a provider the server can reach, while images need
# one that returns the bytes inline — AvalAI rewrites image responses into a
# URL on a host blocked from Iran, so an image generated there is billed and
# then unreachable. Defaults to LLM_PROVIDER when unset.
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "").strip().lower() or LLM_PROVIDER

if LLM_PROVIDER == "openai":
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    # Deliberately ignores OPENAI_BASE_URL: for provider=openai the endpoint
    # IS OpenAI. .env pins that variable to the gateway, so honouring it here
    # would send every request straight back to AvalAI while the logs claimed
    # otherwise.
    #
    # Set explicitly rather than left as None: the OpenAI SDK reads
    # OPENAI_BASE_URL from the environment when no base_url is passed, so
    # None ALSO lands back on the gateway. Naming the endpoint is the only
    # way to be sure which provider is actually being called.
    OPENAI_BASE_URL = "https://api.openai.com/v1"
else:
    OPENAI_API_KEY = os.getenv("AVALAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.avalai.ir/v1")

# Guided EFT chatbot — ~12 calls per participant, the bulk of token spend.
CHAT_MODEL = os.getenv("CHAT_MODEL", "gpt-5-mini")

# Writes the image prompts + Persian cues from the confirmed episode.
PROMPT_MODEL = os.getenv("PROMPT_MODEL", "gpt-5-mini")

# Generates the reminder images themselves.
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-2")

# Seconds before a CHAT call is abandoned. Kept well under the frontend's own
# 60s request timeout: an unreachable provider otherwise hangs the whole turn
# past the point where the participant has already seen a connection error,
# and they sit staring at a dead chat box. Failing fast lets the backend send
# its "sorry, let me ask again" reply while anyone is still waiting.
# Image generation is slow by nature and is NOT covered by this.
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "25"))

# One retry, not the SDK's default of two: each retry re-spends the timeout
# above, and three sequential 25s attempts is far past any useful wait.
LLM_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "1"))


def describe_storage() -> str:
    """Where participant data will actually be written, for the boot log.

    The failure this exists to catch is silent and total: if DATA_DIR and the
    database live inside the container instead of on a mounted disk, every
    redeploy wipes them, and nothing about running the app reveals that until
    data is already gone. A container path here is a WARNING, not a detail.
    """
    url = DATABASE_URL
    # Never log Postgres credentials.
    if "@" in url:
        scheme, _, rest = url.partition("://")
        url = f"{scheme}://***@{rest.rpartition('@')[2]}"

    # A process cannot tell whether a path survives redeploys — that depends
    # on the host's storage config (on Chabokan, a «مسیر دائمی» / permanent
    # path). So DATA_PERSISTENT is how you assert it, and the path check below
    # is only a guess for when nobody has said.
    declared = os.getenv("DATA_PERSISTENT", "").strip().lower()
    if declared in ("1", "true", "yes"):
        note = "  (declared persistent)"
        ephemeral = False
    elif declared in ("0", "false", "no"):
        note = ""
        ephemeral = True
    else:
        note = ""
        ephemeral = (
            DATABASE_URL.startswith("sqlite")
            and not str(DATA_DIR).startswith(
                ("/data", "/mnt", "/var/lib/data"))
        )

    warn = ""
    if ephemeral:
        warn = ("\n⚠️  DATA IS EPHEMERAL: DATA_DIR does not look like "
                "persistent storage. Every redeploy will DELETE the database "
                "and all generated reminder images.\n"
                "    On Chabokan: add a permanent path (مسیرهای دائمی) for "
                "this directory, then set DATA_PERSISTENT=true to silence "
                "this once it is really configured.")
    return f"data_dir={DATA_DIR}{note} db={url} debug={DEBUG_MODE}{warn}"


def describe_llm() -> str:
    """One-line summary of the active LLM config, for the boot log.

    Never includes the key itself — only whether one was found. A missing key
    degrades the app silently (canned chat questions, no images), so it needs
    to be visible at startup rather than discovered from odd behaviour.
    """
    note = ""
    if LLM_PROVIDER == "openai" and OPENAI_API_KEY \
            and not OPENAI_API_KEY.startswith("sk-"):
        # Gateway keys (AvalAI's start 'aa-') are a common copy-paste mistake
        # here and produce an opaque 401 against OpenAI.
        note = "  ⚠️ key does not look like an OpenAI key (expected 'sk-…')"
    img_key, img_base = _image_credentials()
    return (
        f"LLM provider={LLM_PROVIDER} "
        f"base_url={OPENAI_BASE_URL or 'openai-default'} "
        f"key={'set' if OPENAI_API_KEY else 'MISSING'} "
        f"chat={CHAT_MODEL} prompt={PROMPT_MODEL}\n"
        f"🖼️ image provider={IMAGE_PROVIDER} base_url={img_base} "
        f"key={'set' if img_key else 'MISSING'} model={IMAGE_MODEL}"
        f"{note}"
    )


def openai_client():
    """The app's single OpenAI-client factory: applies OPENAI_BASE_URL so
    every call site reaches the same provider. Returns None when no key is
    configured (callers fall back to non-LLM behaviour)."""
    if not OPENAI_API_KEY:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None
    try:
        return OpenAI(
            api_key=OPENAI_API_KEY,
            base_url=OPENAI_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
            max_retries=LLM_MAX_RETRIES,
        )
    except Exception:
        return None


def _image_credentials() -> tuple[str | None, str]:
    """Key and endpoint for IMAGE_PROVIDER, which may differ from chat's."""
    if IMAGE_PROVIDER == "openai":
        return os.getenv("OPENAI_API_KEY"), "https://api.openai.com/v1"
    if IMAGE_PROVIDER == "avalai":
        return (os.getenv("AVALAI_API_KEY") or os.getenv("OPENAI_API_KEY"),
                os.getenv("OPENAI_BASE_URL", "https://api.avalai.ir/v1"))
    # Unrecognised value: fall back to whatever chat is using rather than
    # silently disabling image generation.
    return OPENAI_API_KEY, OPENAI_BASE_URL


def image_client():
    """Client for image generation.

    Separate from openai_client() for two reasons: it may target a different
    provider (see IMAGE_PROVIDER), and it gets no chat timeout — generation
    legitimately runs for minutes, and LLM_TIMEOUT_SECONDS would abort every
    single one.
    """
    key, base_url = _image_credentials()
    if not key:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None
    try:
        return OpenAI(api_key=key, base_url=base_url,
                      timeout=600.0, max_retries=LLM_MAX_RETRIES)
    except Exception:
        return None


# ─────────────────────────────
# SECRETS
# ─────────────────────────────
# Anything guarding participant data is allowed a convenient dev default, but
# never once DEBUG_MODE is off: a deployed server with a published default
# SECRET_KEY lets anyone forge a login token, and a default export key hands
# out the whole dataset. Better to refuse to boot than to run wide open.

def _require_secret(name: str, dev_default: str) -> str:
    value = os.getenv(name)
    if value:
        return value
    if DEBUG_MODE:
        return dev_default
    raise RuntimeError(
        f"{name} must be set when DEBUG_MODE is off. "
        f"Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
    )


# JWT / Auth settings
SECRET_KEY = _require_secret("SECRET_KEY", "supersecretkey")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# Expiry (in minutes)

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 120))
ACCESS_TOKEN_EXPIRE_DELTA = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

# ─────────────────────────────
# OTHER OPTIONAL SETTINGS
# ─────────────────────────────

APP_NAME = os.getenv("APP_NAME", "moirai Research Backend")

# ─────────────────────────────
# RESEARCH CONDITIONS
# ─────────────────────────────
# ─────────────────────────────
# STUDY DESIGN — BETWEEN SUBJECTS
# ─────────────────────────────
# Each participant is assigned ONE arm at signup and stays in it:
#
#   "eft"     – guided EFT chat, then their own personalized reminder image
#   "control" – no chat, no personal image; the shared generic reminders
#
# Both arms are interrupted identically and answer the same closing
# questionnaire, so the only thing that differs is whether the intervention
# is personal to them. A control that saw no reminders at all would make the
# comparison "any reminder vs none", which is a different question.
EFT_GROUP_RATIO = float(os.getenv("EFT_GROUP_RATIO", "0.5"))

# Superseded by the between-subjects design above: the per-trigger
# personalized-vs-generic split now follows study_group, not a coin flip, so
# a participant's exposure is consistent for the whole study.
#
# Kept (default 0) so the within-participant machinery still exists and can
# be switched back on without rebuilding it. Non-zero only has any effect for
# participants in the "eft" arm.
NEUTRAL_RATIO = float(os.getenv("NEUTRAL_RATIO", "0.0"))

# ─────────────────────────────
# SCHEDULED CUE PROTOCOL
# ─────────────────────────────
# Reminders are delivered on a FIXED CLOCK, not in reaction to disengagement.
#
# This is the change that makes the analysis work. A cue that fires *because*
# the participant got distracted can never predict whether they get
# distracted — the design was circular. On a fixed schedule the cue is
# exogenous: it lands whether or not they were about to disengage, so it
# becomes a legitimate predictor and the before/after contrast within one
# participant is valid. Equal dosage across arms is the visible benefit; this
# is the one that matters.
#
# The SERVER owns this clock. Neither client can be trusted with it: the web
# app's timers are throttled by the browser once its tab is hidden — exactly
# the state where a cue matters most — and the extension's MV3 service worker
# is evicted and restarted at Chrome's discretion.

# Length of the reading window. Two authentic IELTS Academic Reading passages
# in 35 minutes is tighter than real IELTS pace (~20 min per passage), which
# is deliberate: mild time pressure makes the task aversive enough that
# natural disengagement occurs, without which the primary measures have no
# variance to explain.
READING_WINDOW_SECONDS = int(os.getenv("READING_WINDOW_SECONDS", "2100"))

# When each cue is due, as offsets from the start of the reading window.
# Exactly two, so intervention dosage is identical in both arms.
CUE_OFFSETS_SECONDS = [
    int(x) for x in os.getenv("CUE_OFFSETS_SECONDS", "600,1200").split(",")
]

# How long after a slot opens the cue may still be delivered. Covers the case
# where the participant is sitting on a page the extension cannot inject into
# (chrome://, the PDF viewer, the Web Store) — the extension keeps retrying
# within this window. After it expires the row is marked undelivered WITH A
# REASON rather than silently dropped, because "no cue was needed" and
# "delivery failed" must not look the same in the data.
CUE_GRACE_SECONDS = int(os.getenv("CUE_GRACE_SECONDS", "90"))

# Silence after which a participant counts as idle. Mirrors StudyConfig in
# the Flutter app; both must agree, because this defines what counts as a
# disengagement and therefore what the outcome measures mean.
IDLE_THRESHOLD_SECONDS = int(os.getenv("IDLE_THRESHOLD_SECONDS", "60"))

# Retention windows are unequal by construction: slot 1 has at most 10
# minutes before slot 2 lands, slot 2 has 15 before the session ends. Left
# uncorrected, slot 2 would look better purely for having more room. Analysis
# censors both at this common horizon.
RETENTION_CENSOR_SECONDS = int(os.getenv("RETENTION_CENSOR_SECONDS", "600"))

# Key required by GET /api/research/export — the full dataset export.
ADMIN_EXPORT_KEY = _require_secret("ADMIN_EXPORT_KEY", "moirai-export-2026")
