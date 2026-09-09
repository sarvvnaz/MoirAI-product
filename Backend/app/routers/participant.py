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
    has_feedback = (
        db.query(models.StudyFeedback)
        .filter(models.StudyFeedback.user_id == current_user.id)
        .first()
        is not None
    )

    group = current_user.study_group or "eft"
    # The control arm never does the EFT chat, so an episode is not part of
    # its route. Reusing the same stage machine for both arms — rather than
    # branching the whole flow — keeps resume behaviour identical and means
    # only this one condition encodes the difference.
    needs_episode = group == "eft"

    if not has_profile:
        stage = "profile"
    elif needs_episode and not has_episode:
        stage = "eft_chat"
    elif completed_sessions == 0:
        stage = "session1"
    elif completed_sessions == 1:
        stage = "session2"
    elif not has_feedback:
        stage = "feedback"
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
