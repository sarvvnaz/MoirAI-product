"""Event-level research data (work step 11).

One ResearchEvent row PER TRIGGER (tab_switch / idle). Rows are created at
trigger time — if the participant closes everything mid-session, the data up
to that moment is already persisted. Return info is patched onto the latest
open row; each new trigger (and session end) closes out the previous row's
reading-time window.
"""

from __future__ import annotations

import io
import json
import time
import random
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import ADMIN_EXPORT_KEY, NEUTRAL_RATIO, REMINDERS_DIR
from app.database import models
from app.database.db_setup import get_db
from app.services.security import get_current_user

router = APIRouter(prefix="/api/research", tags=["Research"])


def pick_condition(user: models.User) -> str:
    """The condition for THIS participant — decided by their study arm.

    Between-subjects: a participant is in one arm for the whole study and
    never sees the other's stimulus. This used to flip a coin per trigger,
    which was the earlier within-participant design; leaving it in place
    meant the logged condition drifted away from what the participant was
    actually shown, even after the arms themselves were separated.
    """
    return "neutral" if (user.study_group or "eft") == "control" else "personalized"


def _utcnow() -> datetime:
    """Timezone-aware UTC now.

    The timestamp columns are DateTime(timezone=True), which Postgres returns
    as AWARE datetimes while SQLite returns them NAIVE. Subtracting a naive
    utcnow() from an aware column raises TypeError, so this worked throughout
    development on SQLite and began failing on every /event/return the moment
    the study moved to Postgres — losing return latency, a primary outcome
    measure, while the rest of the app looked healthy.
    """
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Treat a stored naive timestamp as UTC so the two are comparable.

    Rows written under SQLite are naive and rows written under Postgres are
    aware; both must subtract cleanly, including rows that predate the
    migration.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _active_session_id(db: Session, user_id: int) -> int | None:
    s = (
        db.query(models.Session)
        .filter(models.Session.user_id == user_id,
                models.Session.ended_at.is_(None))
        .order_by(models.Session.started_at.desc())
        .first()
    )
    return s.id if s else None


def _latest_open_event(db: Session, user_id: int) -> models.ResearchEvent | None:
    """The most recent trigger that hasn't been marked returned yet."""
    return (
        db.query(models.ResearchEvent)
        .filter(models.ResearchEvent.participant_id == user_id,
                models.ResearchEvent.returned_to_reading == 0)
        .order_by(models.ResearchEvent.event_timestamp.desc())
        .first()
    )


def _close_previous_window(db: Session, user_id: int, now: datetime) -> None:
    """A new trigger arrived: the previous returned event's reading window
    ends now → fill reading_time_after_return + repeated_disengagement."""
    prev = (
        db.query(models.ResearchEvent)
        .filter(models.ResearchEvent.participant_id == user_id,
                models.ResearchEvent.returned_to_reading == 1,
                models.ResearchEvent.reading_time_after_return.is_(None))
        .order_by(models.ResearchEvent.event_timestamp.desc())
        .first()
    )
    if prev is not None and prev.return_timestamp is not None:
        delta = (_aware(now) - _aware(prev.return_timestamp)).total_seconds()
        prev.reading_time_after_return = max(0.0, delta)
        prev.repeated_disengagement_after_return = 1


@router.post("/event", status_code=status.HTTP_201_CREATED)
def create_event(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Creates one trigger row. Body:
      { "event_type": "tab_switch" | "idle",
        "reminder_shown": bool (optional — in-app overlays know immediately) }
    """
    event_type = (data.get("event_type") or "").strip()
    if event_type not in ("tab_switch", "idle"):
        raise HTTPException(status_code=422, detail="event_type must be tab_switch or idle")

    now = _utcnow()
    _close_previous_window(db, current_user.id, now)

    event = models.ResearchEvent(
        participant_id=current_user.id,
        session_id=_active_session_id(db, current_user.id),
        event_type=event_type,
        event_timestamp=now,
        condition_assigned=pick_condition(current_user),
        reminder_shown_timestamp=now if data.get("reminder_shown") else None,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return {"ok": True, "event_id": event.id,
            "condition": event.condition_assigned}


@router.post("/event/reminder-shown", status_code=status.HTTP_200_OK)
def mark_reminder_shown(
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Called (by the extension) when its overlay is actually displayed —
    stamps reminder_shown_timestamp on the latest open trigger.

    Body: {"condition": "personalized" | "neutral"} — which arm the client
    believes it displayed.

    The participant's ARM decides what gets recorded, not this report. The
    server withholds the other arm's images entirely, so the client cannot
    show anything else; a disagreement therefore means a stale extension or a
    bug, and recording the client's version would quietly move a participant
    between arms in the data. It is logged loudly instead.

    (An earlier revision let the client win. That was right while the design
    randomised per trigger and the client did the rolling — it is wrong now
    that the arm is fixed per participant and enforced server-side.)
    """
    event = _latest_open_event(db, current_user.id)
    if event is None:
        return {"ok": False, "detail": "no open trigger"}

    expected = pick_condition(current_user)
    shown = (data or {}).get("condition")
    if shown is not None and shown != expected:
        print(f"⚠️ reminder-shown: client reported {shown!r} but participant "
              f"{current_user.id} is in arm {expected!r} — recording the arm. "
              f"A stale extension can cause this; the arms are enforced "
              f"server-side, so it should not happen otherwise.")
    event.condition_assigned = expected

    if event.reminder_shown_timestamp is None:
        event.reminder_shown_timestamp = _utcnow()
    db.commit()
    return {"ok": True, "event_id": event.id,
            "condition": event.condition_assigned}


@router.post("/event/return", status_code=status.HTTP_200_OK)
def mark_return(
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    The participant is back at the reading. Patches the latest open trigger:
      { "dismissed": bool (tapped the overlay away),
        "clicked_return": bool (used the overlay's return button) }
    Latency is computed server-side.
    """
    event = _latest_open_event(db, current_user.id)
    if event is None:
        return {"ok": False, "detail": "no open trigger"}

    now = _utcnow()
    event.returned_to_reading = 1
    event.return_timestamp = now
    event.return_latency_seconds = max(
        0.0, (_aware(now) - _aware(event.event_timestamp)).total_seconds())
    if (data or {}).get("dismissed"):
        event.dismissed = 1
    if (data or {}).get("clicked_return"):
        event.clicked_return = 1
    db.commit()
    return {"ok": True, "event_id": event.id,
            "latency": event.return_latency_seconds}


@router.post("/session-closed", status_code=status.HTTP_200_OK)
def session_closed(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Session ended: close the last returned event's reading window with
    repeated_disengagement = false (no further trigger followed)."""
    now = _utcnow()
    prev = (
        db.query(models.ResearchEvent)
        .filter(models.ResearchEvent.participant_id == current_user.id,
                models.ResearchEvent.returned_to_reading == 1,
                models.ResearchEvent.reading_time_after_return.is_(None))
        .order_by(models.ResearchEvent.event_timestamp.desc())
        .first()
    )
    if prev is not None and prev.return_timestamp is not None:
        prev.reading_time_after_return = max(
            0.0, (_aware(now) - _aware(prev.return_timestamp)).total_seconds())
        prev.repeated_disengagement_after_return = 0
        db.commit()
    return {"ok": True}


# ─────────────────────────────
# EXPORT (research data dump)
# ─────────────────────────────
def _require_export_key(x_export_key: str | None = Header(default=None)) -> None:
    """Gate for the dataset exports.

    The key travels in a header, never the query string: query strings are
    written to server access logs, proxy logs and browser history, and this
    one key unlocks every participant's data.

        curl -H "X-Export-Key: $ADMIN_EXPORT_KEY" https://host/api/research/export
    """
    if not x_export_key or x_export_key != ADMIN_EXPORT_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing X-Export-Key header")


def _dataset(db: Session) -> dict:
    """Every research-relevant table, JSON-serialisable.

    password_hash is excluded — nothing downstream needs it and an export
    tends to end up in more places than the database does.
    """

    def rows(model, exclude=()):
        out = []
        for r in db.query(model).all():
            d = {}
            for c in model.__table__.columns:
                if c.name in exclude:
                    continue
                v = getattr(r, c.name)
                d[c.name] = v.isoformat() if isinstance(v, datetime) else v
            out.append(d)
        return out

    return {
        "exported_at": _utcnow().isoformat(),
        "users": rows(models.User, exclude=("password_hash",)),
        "participant_profiles": rows(models.ParticipantProfile),
        "eft_episodes": rows(models.EFTEpisode),
        "sessions": rows(models.Session),
        "research_events": rows(models.ResearchEvent),
        "study_feedback": rows(models.StudyFeedback),
        "event_logs": rows(models.EventLog),
        "reminder_assets": rows(models.ReminderAsset),
        "measure_responses": rows(models.MeasureResponse),
        # The closing outcome measure, and the arm each answer belongs to.
    }


@router.get("/storagecheck", dependencies=[Depends(_require_export_key)])
def storagecheck(db: Session = Depends(get_db)):
    """Does DATA_DIR actually survive a redeploy? Answers it with evidence.

    DATA_PERSISTENT only silences a warning; it asserts nothing. The way to
    know is a marker file written once and read back after a redeploy:

        1. call this endpoint, note marker_created
        2. redeploy
        3. call it again

    Same marker_created and the same boot_id absent → storage persisted.
    A NEW marker_created means the directory was wiped, whatever the panel
    or the env var says.
    """
    from app.config import DATA_DIR, DATABASE_URL, REMINDERS_DIR

    marker = DATA_DIR / ".persistence_marker"
    fresh = False
    if not marker.exists():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(_utcnow().isoformat())
        fresh = True

    try:
        created = marker.read_text().strip()
    except Exception as e:
        created = f"unreadable: {e}"

    db_path = None
    db_size = None
    if DATABASE_URL.startswith("sqlite"):
        p = Path(DATABASE_URL.split("sqlite:///", 1)[-1])
        if not str(p).startswith("/"):
            p = Path("/" + str(p))
        db_path, db_size = str(p), (p.stat().st_size if p.exists() else 0)

    return {
        "data_dir": str(DATA_DIR),
        "marker_created": created,
        "marker_created_now": fresh,
        "verdict": ("Marker was just created. If this says true again after a "
                    "redeploy, DATA_DIR is NOT persistent."
                    if fresh else
                    "Marker survived from an earlier boot — storage IS "
                    "persisting so far."),
        "database": {"path": db_path, "bytes": db_size,
                     "users": db.query(models.User).count()},
        "reminder_images": sorted(
            p.name for p in REMINDERS_DIR.glob("*.png")
        ) if REMINDERS_DIR.is_dir() else [],
        "files_in_data_dir": sorted(
            p.name for p in DATA_DIR.iterdir()
        ) if DATA_DIR.is_dir() else [],
    }


@router.get("/netcheck", dependencies=[Depends(_require_export_key)])
def netcheck(host: str = "image-proxy-worker.gnbellosc.workers.dev"):
    """Can this server reach the image CDN, and over which IP family?

    Diagnostic for the one failure that costs a generated image after it has
    already been paid for: "[Errno 99] Cannot assign requested address" when
    downloading. That is a local bind failure, so the question is whether the
    container resolves IPv6 addresses it has no route to.

    Exists because the hosting panel's console is not always reachable, and
    this is otherwise unanswerable from outside the container. Key-gated: it
    takes a host parameter, so it must not be open to the internet.
    """
    import socket

    out: dict = {"host": host, "resolved": {"ipv4": [], "ipv6": []}}
    try:
        for fam, _, _, _, addr in socket.getaddrinfo(host, 443):
            key = "ipv6" if fam == socket.AF_INET6 else "ipv4"
            if addr[0] not in out["resolved"][key]:
                out["resolved"][key].append(addr[0])
    except Exception as e:
        out["resolved"]["error"] = f"{type(e).__name__}: {e}"

    def probe(family) -> dict:
        s = None
        try:
            infos = socket.getaddrinfo(host, 443, family)
            if not infos:
                return {"ok": False, "detail": "no address of this family"}
            addr = infos[0][4]
            s = socket.socket(family, socket.SOCK_STREAM)
            s.settimeout(10)
            started = time.time()
            s.connect(addr)
            return {"ok": True, "addr": addr[0],
                    "seconds": round(time.time() - started, 2)}
        except Exception as e:
            return {"ok": False, "detail": f"{type(e).__name__}: {e}"}
        finally:
            if s is not None:
                s.close()

    out["connect_ipv4"] = probe(socket.AF_INET)
    out["connect_ipv6"] = probe(socket.AF_INET6)

    v4, v6 = out["connect_ipv4"]["ok"], out["connect_ipv6"]["ok"]
    if v4 and not v6 and out["resolved"]["ipv6"]:
        out["verdict"] = ("IPv6 addresses resolve but cannot be connected to; "
                          "IPv4 works. This is the Errno 99 cause, and forcing "
                          "IPv4 on the download is the right fix.")
    elif v4:
        out["verdict"] = "IPv4 reachable — the CDN is not the problem."
    else:
        out["verdict"] = ("Cannot reach the CDN at all on either family — the "
                          "host itself is blocked or unreachable from here.")
    return out


@router.get("/export", dependencies=[Depends(_require_export_key)])
def export_data(db: Session = Depends(get_db)):
    """Dumps all research-relevant tables as JSON."""
    return _dataset(db)


@router.get("/export/archive", dependencies=[Depends(_require_export_key)])
def export_archive(db: Session = Depends(get_db)):
    """The same tables PLUS the generated reminder images, as one .zip.

    reminder_assets only stores image URLs; the PNGs themselves live on the
    data disk. An export of the rows alone is not a complete record of what
    each participant was actually shown, so the archive carries both:

        data.json           the full table dump
        reminders/*.png     every generated image, filename as referenced
                            by reminder_assets.image_url
    """
    buf = io.BytesIO()
    # Images are PNG (already compressed) and the JSON is small, so DEFLATE
    # costs little and keeps the download manageable.
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "data.json",
            json.dumps(_dataset(db), ensure_ascii=False, indent=2),
        )
        if REMINDERS_DIR.is_dir():
            for img in sorted(REMINDERS_DIR.iterdir()):
                if img.is_file() and not img.name.startswith("."):
                    zf.write(img, f"reminders/{img.name}")

    buf.seek(0)
    stamp = _utcnow().strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="moirai-export-{stamp}.zip"'
        },
    )
