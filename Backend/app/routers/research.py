"""Research data export, and the FROZEN reactive-protocol event routes.

The /event* routes below belong to the superseded design, in which a reminder
fired *because* the participant disengaged. That made the analysis circular: a
cue triggered by a disengagement can never predict whether a disengagement
happens. Cues are now delivered on a fixed clock (app/routers/cues.py), which
makes them exogenous and the before/after contrast valid.

The routes are KEPT AND ACCEPT CALLS, but no longer write. During the
transition a participant may still be running an older extension build, and a
404 there would break their session — a silent no-op does not. Nothing is
recorded because ResearchEvent rows come from a different protocol and must
never be mixed with the new tables.

Everything still worth logging goes to CueDelivery and DisengagementEpisode.
"""

from __future__ import annotations

import csv
import io
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.config import ADMIN_EXPORT_KEY, REMINDERS_DIR
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


# ──────────────────────────────────────────────────────────────────────
# FROZEN ROUTES — accepted, never written
# ──────────────────────────────────────────────────────────────────────
# Each returns ok:false with a reason so a stale client degrades quietly
# instead of erroring, and so anything still calling them is visible in the
# logs rather than silently assumed to be gone.

def _frozen(route: str, user_id: int) -> dict:
    print(f"ℹ️ {route} called by participant {user_id} — reactive protocol is "
          f"frozen, nothing written. This client is running an old build; "
          f"scheduled cues are served from /api/study/cue/*.")
    return {"ok": False, "detail": "reactive protocol frozen", "route": route}


@router.post("/event", status_code=status.HTTP_200_OK)
def create_event(
    data: dict | None = None,
    current_user: models.User = Depends(get_current_user),
):
    """FROZEN. Disengagements now go to POST /api/study/disengagement/start."""
    return _frozen("/event", current_user.id)


@router.post("/event/reminder-shown", status_code=status.HTTP_200_OK)
def mark_reminder_shown(
    data: dict | None = None,
    current_user: models.User = Depends(get_current_user),
):
    """FROZEN. Delivery is now stamped by POST /api/study/cue/{id}/shown."""
    return _frozen("/event/reminder-shown", current_user.id)


@router.post("/event/return", status_code=status.HTTP_200_OK)
def mark_return(
    data: dict | None = None,
    current_user: models.User = Depends(get_current_user),
):
    """FROZEN. Returns now close an episode via /api/study/disengagement/end,
    which is also where return latency is computed."""
    return _frozen("/event/return", current_user.id)


@router.post("/session-closed", status_code=status.HTTP_200_OK)
def session_closed(
    current_user: models.User = Depends(get_current_user),
):
    """FROZEN. Superseded by POST /api/study/session/end-reading."""
    return _frozen("/session-closed", current_user.id)


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
        # Frozen — the reactive protocol's rows. Exported for the record,
        # never to be pooled with cue_deliveries / disengagement_episodes.
        "research_events": rows(models.ResearchEvent),
        "cue_deliveries": rows(models.CueDelivery),
        "disengagement_episodes": rows(models.DisengagementEpisode),
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


@router.get("/export/measures.csv",
            dependencies=[Depends(_require_export_key)])
def export_measures_csv(db: Session = Depends(get_db)):
    """Long-format questionnaire export, one row per answered item.

    Long rather than wide on purpose: the battery differs by condition and
    changes between versions, so a wide table would be mostly empty columns
    whose meaning depends on which arm the row belongs to.

    `measure_status` and `battery_version` travel on every row so published
    instruments, study-specific HCI items and open-ended prompts can never be
    silently pooled in an analysis — that separation is the one thing the
    write-up cannot recover if it is lost here.
    """
    rows = (
        db.query(models.MeasureResponse, models.User)
        .join(models.User, models.User.id == models.MeasureResponse.user_id)
        .order_by(models.MeasureResponse.user_id,
                  models.MeasureResponse.phase,
                  models.MeasureResponse.id)
        .all()
    )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "participant_id", "participant_code", "condition",
        "battery_version", "phase", "timepoint",
        "instrument", "item_code", "measure_status", "validated_status",
        "source",
        "response_value", "response_text",
        "entered_hours", "entered_minutes", "normalized_total_minutes",
        "scale_min", "scale_max", "reverse_scored",
        "answered_at",
    ])
    for r, u in rows:
        is_duration = r.entered_hours is not None or r.entered_minutes is not None
        w.writerow([
            u.id, u.participant_code, u.study_group or "",
            r.battery_version or "", r.phase if r.phase is not None else "",
            r.timepoint,
            r.instrument, r.item_code, r.measure_status or "",
            int(bool(r.validated)),
            r.source or "",
            r.value if r.value is not None else "",
            (r.text_value or "").replace("\n", " ").strip(),
            r.entered_hours if r.entered_hours is not None else "",
            r.entered_minutes if r.entered_minutes is not None else "",
            # Only meaningful for duration items; blank elsewhere so a reader
            # never mistakes a Likert value for a number of minutes.
            r.value if is_duration else "",
            r.scale_min if r.scale_min is not None else "",
            r.scale_max if r.scale_max is not None else "",
            int(bool(r.reverse)),
            r.created_at.isoformat() if r.created_at else "",
        ])

    buf.seek(0)
    stamp = _utcnow().strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="moirai-measures-{stamp}.csv"'},
    )


@router.get("/export/cues.csv", dependencies=[Depends(_require_export_key)])
def export_cues_csv(db: Session = Depends(get_db)):
    """One row per scheduled cue slot, delivered or not.

    Column names are deliberately DESCRIPTIVE rather than interpretive:
    `return_latency_ms` is the time between an eligible cue event and an
    observed return to the study tab. It is not "motivation", "re-engagement"
    or "motivational recovery" — those are interpretations the analysis may
    argue for, and naming a column after one presumes the finding.
    """
    rows = (
        db.query(models.CueDelivery, models.User)
        .join(models.User, models.User.id == models.CueDelivery.participant_id)
        .order_by(models.CueDelivery.participant_id, models.CueDelivery.slot)
        .all()
    )
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "participant_id", "participant_code", "condition",
        "session_id", "slot", "scheduled_at", "delivered_at",
        "delivery_offset_ms", "state_at_delivery", "form", "cue_condition",
        "dismissed", "clicked_return",
        "return_latency_ms", "post_cue_focus_seconds",
        "not_delivered_reason",
    ])
    for c, u in rows:
        w.writerow([
            u.id, u.participant_code, u.study_group or "",
            c.session_id, c.slot,
            c.scheduled_at.isoformat() if c.scheduled_at else "",
            c.delivered_at.isoformat() if c.delivered_at else "",
            c.delivery_offset_ms if c.delivery_offset_ms is not None else "",
            c.state_at_delivery or "", c.form or "", c.condition or "",
            int(bool(c.dismissed)), int(bool(c.clicked_return)),
            c.return_latency_ms if c.return_latency_ms is not None else "",
            c.post_cue_focus_seconds
            if c.post_cue_focus_seconds is not None else "",
            c.not_delivered_reason or "",
        ])
    buf.seek(0)
    stamp = _utcnow().strftime("%Y%m%d-%H%M%S")
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition":
                 f'attachment; filename="moirai-cues-{stamp}.csv"'},
    )


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
