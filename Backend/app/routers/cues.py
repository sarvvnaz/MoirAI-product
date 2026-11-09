"""Scheduled cue delivery and disengagement telemetry.

THE SERVER OWNS THE CLOCK. Neither client can be trusted with it:

  · the Flutter app's timers are throttled by the browser once its tab is
    hidden — precisely the state in which a cue matters most;
  · the extension's MV3 service worker is evicted and restarted whenever
    Chrome feels like it, so anything it scheduled locally can vanish.

So both clients only ever ASK ("is a slot due?") and RENDER. The server
decides when a slot opens, grants it exactly once, and records what happened.

Two clients race for each slot. They are near-exclusive in practice — the
study tab is either in front (the app answers) or it is not (the extension
answers) — but "near" is not a guarantee, so the grant is settled by a unique
constraint on (session_id, slot) rather than by trusting that exclusivity. A
double-delivered slot would break the equal-dosage claim the design rests on.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import (
    CUE_GRACE_SECONDS,
    CUE_OFFSETS_SECONDS,
    READING_WINDOW_SECONDS,
)
from app.database import models
from app.database.db_setup import get_db
from app.routers.research import pick_condition
from app.services.image_service import generic_reminders
from app.services.security import get_current_user

router = APIRouter(prefix="/api/study", tags=["Cues"])

# Which client rendered the cue.
CLAIMANTS = ("app", "extension")

# Attentional state when the slot opened. The split between these decides
# which primary measure a row contributes to, so the vocabulary is closed.
STATES = ("active", "idle", "off_tab", "off_browser")

# Only these states leave the participant away from the reading, so only
# these can produce a return latency.
AWAY_STATES = ("off_tab", "off_browser")

EPISODE_TYPES = ("tab_switch", "idle")


def _utcnow() -> datetime:
    """Timezone-aware UTC now.

    Aware on purpose: the timestamp columns are DateTime(timezone=True),
    which Postgres hands back aware and SQLite hands back naive. Mixing the
    two raises TypeError on subtraction — the failure that silently cost
    return latency, a primary measure, when this study moved to Postgres.
    """
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    """Read a stored timestamp as UTC whether or not the driver tagged it."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _ms(delta: timedelta) -> int:
    return int(delta.total_seconds() * 1000)


def _active_session(db: Session, user_id: int) -> models.Session | None:
    return (
        db.query(models.Session)
        .filter(models.Session.user_id == user_id,
                models.Session.ended_at.is_(None))
        .order_by(models.Session.started_at.desc())
        .first()
    )


def _assets_for(db: Session, user: models.User) -> list[dict]:
    """The ordered stimulus list for this participant's arm.

    Deterministic by slot: slot 1 always shows asset 1 and slot 2 asset 2,
    identically for every participant. With only two cues in the whole study,
    rotating them would add between-participant stimulus variance on a
    dimension nobody is controlling, in exchange for nothing.
    """
    if (user.study_group or "eft") == "control":
        return [
            {"image_url": g["image_url"], "cue": g.get("cue")}
            for g in generic_reminders()
        ]

    assets = (
        db.query(models.ReminderAsset)
        .filter(models.ReminderAsset.user_id == user.id)
        .filter(models.ReminderAsset.is_generic == False)  # noqa: E712
        .order_by(models.ReminderAsset.asset_index)
        .all()
    )
    return [{"image_url": a.image_url, "cue": a.cue} for a in assets]


def _effective_grace(slot_index: int) -> int:
    """How long slot `slot_index` (1-based) stays claimable.

    CLAMPED so a slot's grace can never run past the moment the NEXT slot
    opens. Two slots being "due" at the same instant is incoherent — there is
    one cue to show and two rows that could claim it — and the failure is
    silent in the worst way: the scan below finds the earlier slot, sees it was
    already delivered, and refuses, so the later cue never fires at all and
    nothing is recorded as having gone wrong.

    This does not bite at the study's real offsets (600s apart, 90s grace) but
    does the moment anyone shortens the offsets to test the protocol without
    waiting twenty minutes — which is exactly when a person is most likely to
    conclude the extension is broken.
    """
    grace = CUE_GRACE_SECONDS
    if slot_index < len(CUE_OFFSETS_SECONDS):
        gap = CUE_OFFSETS_SECONDS[slot_index] - CUE_OFFSETS_SECONDS[slot_index - 1]
        grace = min(grace, max(0, gap))
    return grace


def _slot_due(elapsed_seconds: float) -> int | None:
    """Which slot, if any, is open right now.

    A slot opens at its offset and stays claimable for its effective grace.
    The grace exists for the extension: a participant sitting on a page it
    cannot inject into (chrome://, the PDF viewer, the Web Store) has to be
    retried rather than written off on the first attempt.

    Returns the LATEST open slot. With clamped grace the windows cannot
    overlap, so this is belt-and-braces — but if they ever did, the newer cue
    is the right one to show, and an older exhausted window must never mask it.
    """
    due = None
    for index, offset in enumerate(CUE_OFFSETS_SECONDS, start=1):
        if offset <= elapsed_seconds < offset + _effective_grace(index):
            due = index
    return due


def _lateness_ms(db: Session, row: models.CueDelivery, now: datetime) -> int:
    """How late this cue was, measured against the SESSION clock.

    Derived from reading_started_at + offset rather than from the stored
    scheduled_at column. Those two are meant to describe the same instant, and
    keeping two sources of truth for one instant is how they quietly drift
    apart — at which point the audit column certifies the wrong thing, which
    is worse than having no audit column at all. scheduled_at stays as a
    human-readable convenience in exports; this is the number that counts.
    """
    session = db.query(models.Session).filter(
        models.Session.id == row.session_id).first()
    started = _aware(session.reading_started_at) if session else None
    if started is None:
        return 0
    due = started + timedelta(seconds=CUE_OFFSETS_SECONDS[row.slot - 1])
    return max(0, _ms(now - due))


def _expire_stale(db: Session, session: models.Session, now: datetime) -> None:
    """Mark slots whose grace has run out as undelivered, WITH a reason.

    An undelivered cue must never be indistinguishable from a cue that was
    never scheduled. That distinction is the whole reason the rows are
    created up front.
    """
    started = _aware(session.reading_started_at)
    if started is None:
        return
    elapsed = (now - started).total_seconds()

    stale = (
        db.query(models.CueDelivery)
        .filter(models.CueDelivery.session_id == session.id,
                models.CueDelivery.delivered_at.is_(None),
                models.CueDelivery.not_delivered_reason.is_(None))
        .all()
    )
    for row in stale:
        offset = CUE_OFFSETS_SECONDS[row.slot - 1]
        if elapsed >= offset + _effective_grace(row.slot):
            row.not_delivered_reason = (
                "claimed_not_shown" if row.claimed_at is not None
                else "grace_expired"
            )


# ──────────────────────────────────────────────────────────────────────
# Reading window
# ──────────────────────────────────────────────────────────────────────
@router.post("/session/start-reading", status_code=status.HTTP_201_CREATED)
def start_reading(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Opens the reading window and schedules both cues.

    Creating the CueDelivery rows here — not at delivery time — is what makes
    a failed delivery visible later as a row with a reason rather than as
    silence.

    Idempotent: a page reload must not restart the clock or duplicate slots,
    which would hand that participant more than two cues.
    """
    session = _active_session(db, current_user.id)
    if session is None:
        raise HTTPException(status_code=409, detail="no active session")

    now = _utcnow()
    if session.reading_started_at is not None:
        started = _aware(session.reading_started_at)
        return {
            "ok": True,
            "already_started": True,
            "session_id": session.id,
            "elapsed_ms": _ms(now - started),
            "window_ms": READING_WINDOW_SECONDS * 1000,
        }

    session.reading_started_at = now
    condition = pick_condition(current_user)
    assets = _assets_for(db, current_user)

    for index, offset in enumerate(CUE_OFFSETS_SECONDS, start=1):
        asset = assets[index - 1] if len(assets) >= index else None
        db.add(models.CueDelivery(
            participant_id=current_user.id,
            session_id=session.id,
            slot=index,
            scheduled_at=now + timedelta(seconds=offset),
            condition=condition,
            asset_image_url=(asset or {}).get("image_url"),
            asset_cue=(asset or {}).get("cue"),
            not_delivered_reason=None if asset else "no_asset_available",
        ))

    if len(assets) < len(CUE_OFFSETS_SECONDS):
        # Loud, because a participant with no stimulus still walks the whole
        # protocol and produces rows that look like a delivered-but-ignored
        # cue unless this is recorded.
        print(f"⚠️ participant {current_user.id} (arm "
              f"{current_user.study_group!r}) has only {len(assets)} reminder "
              f"asset(s) for {len(CUE_OFFSETS_SECONDS)} slots — the missing "
              f"slots are marked no_asset_available.")

    db.commit()
    return {
        "ok": True,
        "already_started": False,
        "session_id": session.id,
        "elapsed_ms": 0,
        "window_ms": READING_WINDOW_SECONDS * 1000,
    }


@router.get("/cue/due")
def cue_due(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Is a cue slot open right now? Polled by both clients.

    Read-only apart from expiring stale slots. Returns `due_slot: null` in the
    ordinary case, which is most of the time.
    """
    session = _active_session(db, current_user.id)
    if session is None or session.reading_started_at is None:
        return {"due_slot": None, "elapsed_ms": None, "reading_started": False}

    now = _utcnow()
    started = _aware(session.reading_started_at)
    elapsed = (now - started).total_seconds()

    _expire_stale(db, session, now)
    db.commit()

    slot = _slot_due(elapsed)
    if slot is not None:
        row = (
            db.query(models.CueDelivery)
            .filter(models.CueDelivery.session_id == session.id,
                    models.CueDelivery.slot == slot)
            .first()
        )
        # Already taken (by this client or the other one) — nothing to do.
        if row is None or row.claimed_at is not None:
            slot = None

    expires_in_ms = None
    if slot is not None:
        offset = CUE_OFFSETS_SECONDS[slot - 1]
        expires_in_ms = max(0, _ms(timedelta(
            seconds=offset + _effective_grace(slot) - elapsed)))

    return {
        "reading_started": True,
        "elapsed_ms": _ms(now - started),
        "window_ms": READING_WINDOW_SECONDS * 1000,
        "due_slot": slot,
        "expires_in_ms": expires_in_ms,
    }


@router.post("/cue/claim")
def claim_cue(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Claim the open slot. Granted to exactly one caller.

    Body: {"state": "active"|"idle"|"off_tab"|"off_browser",
           "claimed_by": "app"|"extension"}

    The claimant reports its STATE, which it alone can observe, and that
    decides the cue's form. It does NOT report the condition: the arm decides
    that, server-side. Letting a client name its own condition would let a
    stale extension quietly move a participant between arms in the data.
    """
    state = (data or {}).get("state")
    claimed_by = (data or {}).get("claimed_by")
    if state not in STATES:
        raise HTTPException(status_code=422, detail=f"state must be one of {STATES}")
    if claimed_by not in CLAIMANTS:
        raise HTTPException(status_code=422,
                            detail=f"claimed_by must be one of {CLAIMANTS}")

    session = _active_session(db, current_user.id)
    if session is None or session.reading_started_at is None:
        return {"granted": False, "reason": "reading_not_started"}

    now = _utcnow()
    started = _aware(session.reading_started_at)
    elapsed = (now - started).total_seconds()

    slot = _slot_due(elapsed)
    if slot is None:
        # The common and correct answer outside the two windows. A tab switch
        # on its own no longer shows anything.
        return {"granted": False, "reason": "no_slot_due"}

    row = (
        db.query(models.CueDelivery)
        .filter(models.CueDelivery.session_id == session.id,
                models.CueDelivery.slot == slot)
        .first()
    )
    if row is None:
        return {"granted": False, "reason": "slot_missing"}
    if row.not_delivered_reason == "no_asset_available":
        return {"granted": False, "reason": "no_asset_available"}
    if row.claimed_at is not None:
        return {"granted": False, "reason": "already_claimed"}

    row.claimed_at = now
    row.claimed_by = claimed_by
    row.state_at_delivery = state
    row.form = (
        "corner_card" if state == "active"
        else "in_app_overlay" if state == "idle"
        else "full_page_modal"
    )
    # Re-assert the arm at claim time rather than trusting the row: an arm
    # that changed between scheduling and delivery should follow the
    # participant, and this is the last point where it can be checked.
    row.condition = pick_condition(current_user)

    try:
        db.commit()
    except IntegrityError:
        # The other client won the race between our read and our write.
        db.rollback()
        return {"granted": False, "reason": "already_claimed"}

    return {
        "granted": True,
        "delivery_id": row.id,
        "slot": row.slot,
        "form": row.form,
        "condition": row.condition,
        "asset": {"image_url": row.asset_image_url, "cue": row.asset_cue},
    }


@router.post("/cue/{delivery_id}/shown")
def cue_shown(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The cue is on screen. Stamps delivery time and how late it was.

    delivery_offset_ms turns "the cue fired at minute 10" from an assumption
    into something the data can be checked against — chrome.alarms has a 30s
    floor, and a suspended service worker can add more on top.
    """
    row = (
        db.query(models.CueDelivery)
        .filter(models.CueDelivery.id == delivery_id,
                models.CueDelivery.participant_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="unknown delivery")

    now = _utcnow()
    if row.delivered_at is None:
        row.delivered_at = now
        row.delivery_offset_ms = _lateness_ms(db, row, now)
        row.not_delivered_reason = None
        db.commit()

    return {"ok": True, "delivery_id": row.id,
            "delivery_offset_ms": row.delivery_offset_ms}


@router.post("/cue/{delivery_id}/interaction")
def cue_interaction(
    delivery_id: int,
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """What the participant did with the cue.

    Body: {"dismissed": bool, "clicked_return": bool}

    For an off-tab cue, clicking through to the reading is also the return —
    it closes the open disengagement episode and yields PRIMARY MEASURE 1.
    """
    row = (
        db.query(models.CueDelivery)
        .filter(models.CueDelivery.id == delivery_id,
                models.CueDelivery.participant_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="unknown delivery")

    payload = data or {}
    if payload.get("dismissed"):
        row.dismissed = True
    if payload.get("clicked_return"):
        row.clicked_return = True

    db.commit()
    return {"ok": True, "delivery_id": row.id}


# ──────────────────────────────────────────────────────────────────────
# Disengagement telemetry
# ──────────────────────────────────────────────────────────────────────
@router.post("/disengagement/start", status_code=status.HTTP_201_CREATED)
def disengagement_start(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The participant stopped reading. Body: {"type": "tab_switch"|"idle"}

    Recorded regardless of whether any cue is nearby: disengagement is the
    OUTCOME now, not the trigger. This is also where PRIMARY MEASURE 2 gets
    resolved — the preceding active-state cue's retention window ends here.
    """
    episode_type = (data or {}).get("type")
    if episode_type not in EPISODE_TYPES:
        raise HTTPException(status_code=422,
                            detail=f"type must be one of {EPISODE_TYPES}")

    session = _active_session(db, current_user.id)
    now = _utcnow()

    # An episode already open means the client double-reported (e.g. idle
    # fired and then the tab was switched). Keep the first: they are one
    # continuous absence from the reading, and counting two would inflate
    # the disengagement count, which is itself an outcome.
    open_episode = (
        db.query(models.DisengagementEpisode)
        .filter(models.DisengagementEpisode.participant_id == current_user.id,
                models.DisengagementEpisode.ended_at.is_(None))
        .order_by(models.DisengagementEpisode.started_at.desc())
        .first()
    )
    if open_episode is not None:
        return {"ok": True, "episode_id": open_episode.id, "reopened": False}

    last_cue = None
    if session is not None:
        last_cue = (
            db.query(models.CueDelivery)
            .filter(models.CueDelivery.session_id == session.id,
                    models.CueDelivery.delivered_at.isnot(None))
            .order_by(models.CueDelivery.delivered_at.desc())
            .first()
        )

    episode = models.DisengagementEpisode(
        participant_id=current_user.id,
        session_id=session.id if session else None,
        episode_type=episode_type,
        started_at=now,
        ms_since_last_cue=(
            _ms(now - _aware(last_cue.delivered_at)) if last_cue else None
        ),
        preceded_by_cue_slot=last_cue.slot if last_cue else None,
    )
    db.add(episode)

    # PRIMARY MEASURE 2: a cue delivered while the participant was ACTIVE is
    # asking "does this keep them here?". The answer is the time until they
    # next stop reading, which is now.
    if (last_cue is not None
            and last_cue.state_at_delivery == "active"
            and last_cue.post_cue_focus_seconds is None):
        last_cue.post_cue_focus_seconds = max(
            0.0, (now - _aware(last_cue.delivered_at)).total_seconds())

    db.commit()
    db.refresh(episode)
    return {"ok": True, "episode_id": episode.id, "reopened": False}


@router.post("/disengagement/end")
def disengagement_end(
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The participant is reading again. Closes the open episode.

    Body: {"ended_by": "return"|"session_end"|"abandoned"} (default "return")

    Also resolves PRIMARY MEASURE 1: if the cue that is still open was
    delivered while they were away, the time from that cue to this return is
    the return latency.
    """
    ended_by = (data or {}).get("ended_by") or "return"
    if ended_by not in ("return", "session_end", "abandoned"):
        raise HTTPException(status_code=422, detail="bad ended_by")

    episode = (
        db.query(models.DisengagementEpisode)
        .filter(models.DisengagementEpisode.participant_id == current_user.id,
                models.DisengagementEpisode.ended_at.is_(None))
        .order_by(models.DisengagementEpisode.started_at.desc())
        .first()
    )
    if episode is None:
        return {"ok": False, "detail": "no open episode"}

    now = _utcnow()
    episode.ended_at = now
    episode.ended_by = ended_by
    episode.duration_ms = max(0, _ms(now - _aware(episode.started_at)))

    # PRIMARY MEASURE 1: the cue was shown to someone who had already left,
    # so the question is "does it pull them back?" — measured to this return.
    session_id = episode.session_id
    if session_id is not None and ended_by == "return":
        cue = (
            db.query(models.CueDelivery)
            .filter(models.CueDelivery.session_id == session_id,
                    models.CueDelivery.delivered_at.isnot(None),
                    models.CueDelivery.state_at_delivery.in_(AWAY_STATES),
                    models.CueDelivery.return_latency_ms.is_(None))
            .order_by(models.CueDelivery.delivered_at.desc())
            .first()
        )
        # Only if the cue landed DURING this absence. A cue shown before the
        # episode began did not cause this return, and crediting it would
        # measure the wrong interval entirely.
        if cue is not None:
            delivered = _aware(cue.delivered_at)
            if delivered >= _aware(episode.started_at):
                cue.return_latency_ms = max(0, _ms(now - delivered))

    db.commit()
    return {"ok": True, "episode_id": episode.id,
            "duration_ms": episode.duration_ms}


@router.post("/session/end-reading")
def end_reading(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Closes the reading window: any open episode ends, stale slots expire.

    Without this an episode that ran to the end of the session stays open
    forever and its duration is NULL, which silently removes it from
    time-on-task — biased in favour of participants who disengaged last.
    """
    session = _active_session(db, current_user.id)
    if session is None:
        return {"ok": False, "detail": "no active session"}

    now = _utcnow()
    open_episode = (
        db.query(models.DisengagementEpisode)
        .filter(models.DisengagementEpisode.participant_id == current_user.id,
                models.DisengagementEpisode.ended_at.is_(None))
        .order_by(models.DisengagementEpisode.started_at.desc())
        .first()
    )
    if open_episode is not None:
        open_episode.ended_at = now
        open_episode.ended_by = "session_end"
        open_episode.duration_ms = max(
            0, _ms(now - _aware(open_episode.started_at)))

    _expire_stale(db, session, now)

    # A slot whose window never even opened, because the participant finished
    # before it came due. Distinct from grace_expired (the cue was due and we
    # failed to deliver it) and it must stay distinguishable: this one means
    # the participant received LESS THAN THE FULL DOSAGE, which breaks the
    # equal-exposure assumption for that row and has to be visible in the data
    # rather than inferred from a NULL.
    never_due = (
        db.query(models.CueDelivery)
        .filter(models.CueDelivery.session_id == session.id,
                models.CueDelivery.delivered_at.is_(None),
                models.CueDelivery.not_delivered_reason.is_(None))
        .all()
    )
    for row in never_due:
        row.not_delivered_reason = "session_ended_before_slot"
    if never_due:
        print(f"⚠️ participant {current_user.id} finished the reading window "
              f"before slot(s) {[r.slot for r in never_due]} came due — they "
              f"received fewer than {len(CUE_OFFSETS_SECONDS)} cues.")

    db.commit()
    return {"ok": True}
