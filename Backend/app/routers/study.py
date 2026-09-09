"""Study session feedback routes.

Provides an endpoint to record participants' self-reported feedback after
each study session. The feedback includes Likert ratings for vividness,
accessibility, future-self connection, task focus, and effort, along with
a yes/no indicator of whether the EFT episode came to mind and optional
free-text comments.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database.db_setup import get_db
from app.database import models
from app.services.security import get_current_user

router = APIRouter(prefix="/api/study", tags=["Study"])


@router.post("/feedback", status_code=status.HTTP_201_CREATED)
def save_study_feedback(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Persist a study feedback record. The request body must include at least
    a `session_number` field to associate the feedback with the correct
    session. The remaining fields are optional; missing values will be
    stored as null.

    Expected JSON body:
      {
        "session_number": 1,
        "vividness": 5,
        "accessibility": 6,
        "future_self_connection": 4,
        "task_focus": 5,
        "effort": 4,
        "episode_recall": true,
        "recall_detail": "Came to mind when I struggled",
        "help_comment": "What helped or didn't help?"
      }
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    session_number = data.get("session_number")
    if session_number is None:
        raise HTTPException(status_code=422, detail="Missing session_number")

    # Create feedback record
    feedback = models.StudyFeedback(
        user_id=current_user.id,
        session_number=int(session_number),
        vividness=data.get("vividness"),
        accessibility=data.get("accessibility"),
        future_self_connection=data.get("future_self_connection"),
        task_focus=data.get("task_focus"),
        effort=data.get("effort"),
        episode_recall=data.get("episode_recall"),
        recall_detail=data.get("recall_detail"),
        help_comment=data.get("help_comment"),
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    return {"ok": True, "feedback_id": feedback.id}