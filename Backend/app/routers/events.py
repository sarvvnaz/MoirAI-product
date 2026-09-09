from datetime import datetime

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database.db_setup import get_db
from app.database import models
from app.services.security import get_current_user
from typing import Optional

router = APIRouter(prefix="/api/events", tags=["Events"])
# router = APIRouter(prefix="/sessions", tags=["Sessions"])

def get_open_session(
    db: Session,
    user_id: int,
    session_id: Optional[int] = None,
) -> Optional[models.Session]:
    """
    Returns the currently open session (ended_at IS NULL) for this user.

    If session_id is provided, it will:
      - ensure the session belongs to this user
      - ensure it's still open

    Returns None if no matching open session exists.
    """
    query = db.query(models.Session).filter(
        models.Session.user_id == user_id,
        models.Session.ended_at.is_(None),
    )

    if session_id is not None:
        query = query.filter(models.Session.id == session_id)

    return (
        query
        .order_by(models.Session.started_at.desc())
        .first()
    )
def get_or_create_current_session(db: Session, user_id: int) -> models.Session:
    session = (
        db.query(models.Session)
        .filter(
            models.Session.user_id == user_id,
            models.Session.ended_at.is_(None),
        )
        .order_by(models.Session.started_at.desc())
        .first()
    )

    if session is not None:
        return session

    last_number = (
        db.query(func.coalesce(func.max(models.Session.session_number), 0))
        .filter(models.Session.user_id == user_id)
        .scalar()
    )
    next_number = last_number + 1

    session = models.Session(
        user_id=user_id,
        session_number=next_number,
        started_at=datetime.utcnow(),
    )
    db.add(session)
    db.flush()  # to get session.id
    return session


@router.post("/session/start", status_code=status.HTTP_201_CREATED)
def start_session(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):  # ❌ no -> models.Session here
    """
    Start (or reuse) the current session and return its id + number.
    """
    s = get_or_create_current_session(db, current_user.id)
    db.commit()

    return {
        "session_id": s.id,
        "session_number": s.session_number,
    }

# ──────────────────────────────────────────────────────────────────────────────
# Generic event logger
#  - Frontend sends: { "event_type": "...", "details": {...} }
#  - Distinction:
#      * idle_detected   → idle
#      * focus_lost      → distraction
#      * idle_suppressed → diagnostic only (no counters)
# ──────────────────────────────────────────────────────────────────────────────
@router.post("/log", status_code=status.HTTP_201_CREATED)
def log_generic_event(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
  """
  Logs events like idle_detected, focus_resumed, nudge_shown, focus_lost, etc.
  Updates both UserStats (aggregate across all sessions) and Session (per-session).
  """

  print("🛰 /events/log payload:", data)

  event_type = data.get("event_type")
  if not event_type:
    print("⚠️ Missing event_type!")
    return {"error": "Missing event_type"}

  details = data.get("details", {}) or {}
  user_id = current_user.id
  print(f"📌 event_type={event_type}, user_id={user_id}")

  # 1️⃣ Log raw activity for research
  activity = models.UserActivity(
      user_id=user_id,
      activity_type=event_type,
      extra_data=details,
  )
  db.add(activity)

  # 2️⃣ Ensure UserStats row exists
  stats = (
      db.query(models.UserStats)
      .filter_by(user_id=user_id)
      .first()
  )
  if not stats:
    print(f"ℹ️ Creating UserStats row for user {user_id}")
    stats = models.UserStats(user_id=user_id)
    db.add(stats)

  # 3️⃣ Ensure Session row exists
  session = get_open_session(db, user_id)

  print(
      f"🔢 BEFORE → "
      f"idle={stats.total_idle_count}, "
      f"distraction={stats.total_distraction_count}, "
      f"nudges={stats.total_nudges_shown}, "
      f"refocus60={stats.total_refocus_within_60s}, "
      f"sustained={stats.total_sustained_attention}"
  )

  # ────────────────────────────────────────────────────────────────────────────
  # 4️⃣ Update metrics by event_type
  # ────────────────────────────────────────────────────────────────────────────

  # IDLE = user stopped interacting while app was visible & focused
  if event_type == "idle_detected":
    # Aggregate stats
    stats.total_idle_count = (stats.total_idle_count or 0) + 1
    # Per-session
    if session:
        session.idle_count = (session.idle_count or 0) + 1

    # sustained attention (time since last focus_resumed)
    last_refocus = (
        db.query(models.UserActivity)
        .filter_by(user_id=user_id, activity_type="focus_resumed")
        .order_by(models.UserActivity.created_at.desc())
        .first()
    )
    if last_refocus:
      sustained = (datetime.utcnow() - last_refocus.created_at).total_seconds()
      stats.total_sustained_attention = (
          (stats.total_sustained_attention or 0) + sustained
      )
      if session:
        session.sustained_attention = (session.sustained_attention or 0) + sustained

      db.add(
          models.UserActivity(
              user_id=user_id,
              activity_type="sustained_attention",
              duration_seconds=int(sustained),
              extra_data={"duration": sustained},
          )
      )

  # NUDGE SHOWN = we actually showed a nudge UI to the user
  elif event_type == "nudge_shown":
    stats.total_nudges_shown = (stats.total_nudges_shown or 0) + 1
    if session:
        session.nudges_shown = (session.nudges_shown or 0) + 1

  # DISTRACTION = app lost focus (user left the app)
  elif event_type == "focus_lost":
    stats.total_distraction_count = (stats.total_distraction_count or 0) + 1
    if session:
        session.distraction_count = (session.distraction_count or 0) + 1

  # IDLE SUPPRESSED = we *would* show idle nudge but can't (background / not visible)
  # This is diagnostic only → no counters, just the raw UserActivity log above.
  elif event_type == "idle_suppressed":
    # You can add debug here if needed, but we don't increment idle/distraction counts.
    pass

  # FOCUS RESUMED = user returns to the app after distraction/idle
  elif event_type == "focus_resumed":
    # Check if this was a "quick" refocus after a nudge (<= 60s)
    last_nudge = (
        db.query(models.UserActivity)
        .filter_by(user_id=user_id, activity_type="nudge_shown")
        .order_by(models.UserActivity.created_at.desc())
        .first()
    )
    if last_nudge:
      delta = (datetime.utcnow() - last_nudge.created_at).total_seconds()
      if delta <= 60:
        stats.total_refocus_within_60s = (
            (stats.total_refocus_within_60s or 0) + 1
        )
        if session:
            session.refocus_within_60s = (
                (session.refocus_within_60s or 0) + 1
        )

        db.add(
            models.UserActivity(
                user_id=user_id,
                activity_type="immediate_refocus",
                duration_seconds=int(delta),
                extra_data={"latency": delta},
            )
        )

  # SESSION FEEDBACK = user rating after a session
  elif event_type == "session_feedback":
    rating = details.get("rating", 0) or 0

    # aggregate stats
    total = stats.total_sessions * (stats.avg_feedback_score or 0) + rating
    stats.total_sessions += 1
    stats.avg_feedback_score = (
        total / stats.total_sessions if stats.total_sessions > 0 else 0
    )
    

    # per-session value (latest rating)
    if session:
        session.feedback_score = float(rating)

    # Optionally: end session here if this marks the end of a focus block
    # session.ended_at = datetime.utcnow()
    
    if session  :
        print(
            f"🔢 AFTER  → "
            f"idle={stats.total_idle_count}, "
            f"idle={session.idle_count}, "
            f"dis={session.distraction_count}, "


            f"distraction={stats.total_distraction_count}, "
            f"nudges={stats.total_nudges_shown}, "
            f"refocus60={stats.total_refocus_within_60s}, "
            f"sustained={stats.total_sustained_attention}"
        )
    else: print("⚠️ No open session found!")

  elif event_type == "eft_feedback":
    # Update user info in the database
    db.add(models.UserStats(
        user_id=user_id,
        ratingVividness= details.get("ratingVividness"),
        ratingSpecificity= details.get("ratingSpecificity"),
        ratingDifficulty= details.get("ratingDifficulty"),
        ratingGoalImportance= details.get("ratingGoalImportance"),
    ))
  elif event_type == "user_info":
    # Update user info in the database
    db.query(models.User).filter(models.User.id == user_id).update({
        "age": details.get("age"),
        "gender": details.get("gender"),
        "degree": details.get("degree"),
        "examGoal": details.get("examGoal"),
        "studyHoursPerWeek": details.get("studyHoursPerWeek"),
    })
     
  db.commit()
  print(f"✅ Logged {event_type} for user {user_id}")
  return {"message": f"{event_type} logged successfully"}


@router.post("/end_session", status_code=status.HTTP_200_OK)
def end_session(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Marks the user's current open session as ended."""
    user_id = current_user.id

    # Find the active session
    session = (
        db.query(models.Session)
        .filter(models.Session.user_id == user_id, models.Session.ended_at.is_(None))
        .first()
    )

    if not session:
        return {"message": "No active session to end."}

    session.ended_at = datetime.utcnow()
    db.commit()

    print(f"🟢 Session {session.session_number} closed for user {user_id}")

    return {"message": "Session ended successfully"}


