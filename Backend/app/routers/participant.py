"""Participant routes for baseline/demographics collection.

This module defines a simple endpoint for saving a participant's
baseline demographic and study context information. It creates or
updates a ParticipantProfile record tied to the current user.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.db_setup import get_db
from app.database import models
from app.services.security import get_current_user

router = APIRouter(prefix="/api/participant", tags=["Participant"])


@router.post("/profile", status_code=status.HTTP_200_OK)
def save_profile(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Create or update the participant's baseline profile. The request body
    should contain keys corresponding to the ParticipantProfile fields:

    - age
    - education_level
    - study_field
    - english_goal
    - english_level
    - study_frequency
    - english_importance

    If a profile already exists for the user, the record is updated; otherwise
    a new one is created.
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # Find existing profile, if any
    profile = (
        db.query(models.ParticipantProfile)
        .filter(models.ParticipantProfile.user_id == current_user.id)
        .first()
    )

    if profile is None:
        profile = models.ParticipantProfile(user_id=current_user.id)
        db.add(profile)

    # Gender lives on the User row (used by image generation; only زن/مرد
    # are ever passed to the generator — others mean "don't specify").
    if data.get("gender") is not None:
        current_user.gender = data.get("gender")

    # Update fields if present; missing fields leave prior values unchanged
    profile.age = data.get("age", profile.age)
    profile.education_level = data.get("education_level", profile.education_level)
    profile.study_field = data.get("study_field", profile.study_field)
    profile.english_goal = data.get("english_goal", profile.english_goal)
    profile.english_level = data.get("english_level", profile.english_level)
    profile.study_frequency = data.get("study_frequency", profile.study_frequency)
    profile.english_importance = data.get(
        "english_importance", profile.english_importance
    )

    db.commit()
    db.refresh(profile)

    return {"ok": True}


@router.get("/state", status_code=status.HTTP_200_OK)
def get_state(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Returns the participant's current position in the study flow so the
    frontend can resume at the right screen after login.

    Stages, in order:
      profile   -> baseline profile not yet filled
      eft_chat  -> no confirmed EFT episode yet
      session1  -> episode exists, no completed session
      session2  -> one session completed
      feedback  -> both sessions completed, no feedback yet
      done      -> feedback submitted
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    has_profile = (
        db.query(models.ParticipantProfile)
        .filter(models.ParticipantProfile.user_id == current_user.id)
        .first()
        is not None
    )
    has_episode = (
        db.query(models.EFTEpisode)
        .filter(models.EFTEpisode.user_id == current_user.id)
        .first()
        is not None
    )
    completed_sessions = (
        db.query(models.Session)
        .filter(
            models.Session.user_id == current_user.id,
            models.Session.ended_at.isnot(None),
        )
        .count()
    )
    # The v3 open-ended feedback block. Completion is read from the measures
    # table, NOT from the legacy StudyFeedback row: that row was written by
    # the old slider page, which is no longer in the flow. Leaving the gate
    # pointed at it would mean the stage never advances past "feedback" and
    # the participant loops on the last page forever.
    has_feedback = (
        db.query(models.MeasureResponse)
        .filter(models.MeasureResponse.user_id == current_user.id,
                models.MeasureResponse.timepoint == "feedback")
        .first()
        is not None
    )

    group = current_user.study_group or "eft"

    def answered(timepoint: str) -> bool:
        """Has any item at this timepoint been answered?

        Read from stored answers rather than a completion flag, so someone
        who abandons a page half way is returned to it rather than carried
        past it.
        """
        return (
            db.query(models.MeasureResponse)
            .filter(models.MeasureResponse.user_id == current_user.id,
                    models.MeasureResponse.timepoint == timepoint)
            .first()
            is not None
        )

    # The visualization screen has nothing to save, so its completion is
    # marked with an activity row rather than a questionnaire answer. Using a
    # dummy measure item instead would put a non-question into the battery
    # and into every export.
    seen_visualization = (
        db.query(models.UserActivity)
        .filter(models.UserActivity.user_id == current_user.id,
                models.UserActivity.activity_type == "visualization_seen")
        .first()
        is not None
    )

    has_assets = (
        db.query(models.ReminderAsset)
        .filter(models.ReminderAsset.user_id == current_user.id)
        .filter(models.ReminderAsset.is_generic == False)  # noqa: E712
        .first()
        is not None
    )

    # ── the single participant path ──
    #
    # profile → future_goal → pre → chat → generate → visualize → post → done
    #
    # ONE path for everyone. This version has no control arm, so `study_group`
    # is still recorded (assigned at signup, and old rows depend on it) but no
    # longer routes anything — a control participant would otherwise be sent
    # to a chatbot step their arm was built to skip.
    #
    # The reading task, scheduled cues and extension steps are not reachable
    # from here. Their code, routes and tables are untouched and still tested;
    # they are simply not part of this flow.
#     if not has_profile:
#         stage = "profile"
#     # The goal comes BEFORE the pre-questionnaire: the instrumentality items
#     # ask about "this future goal", so without it they have no referent.
#     elif not answered("future_goal"):
#         stage = "future_goal"
#     elif not answered("pre"):
#         stage = "pre"
    # Product: the chatbot collects the goal; research questionnaires are paused.
    if not has_episode:
        stage = "eft_chat"
    # Generation is its own stage so the visualization screen never opens on a
    # missing image.
    elif not has_assets:
        stage = "generate"
    elif not seen_visualization:
        stage = "visualize"
    # elif not answered("post"):
    #     stage = "post"
    elif completed_sessions == 0:
        stage = "reading"
    else:
        stage = "done"

    return {
        "stage": stage,
        "study_group": group,
        "has_profile": has_profile,
        "has_episode": has_episode,
        "completed_sessions": completed_sessions,
        "has_feedback": has_feedback,
    }


@router.post("/visualization-seen", status_code=status.HTTP_201_CREATED)
def mark_visualization_seen(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Record that the participant finished the visualization screen.

    Idempotent: a reload or a double tap must not add a second row, or the
    activity log stops being a record of what happened.
    """
    existing = (
        db.query(models.UserActivity)
        .filter(models.UserActivity.user_id == current_user.id,
                models.UserActivity.activity_type == "visualization_seen")
        .first()
    )
    if existing is None:
        db.add(models.UserActivity(
            user_id=current_user.id,
            activity_type="visualization_seen",
        ))
        db.commit()
    return {"ok": True}
