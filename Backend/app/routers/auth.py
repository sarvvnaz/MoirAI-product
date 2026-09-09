from __future__ import annotations

import random

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.schemas import UserCreate, UserLogin
from app.database.db_setup import get_db
from app.config import EFT_GROUP_RATIO
from app.database import models
from app.services.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Note: the user-chosen ID is stored in the `participant_code` column and is
# only a login handle. All research data (DB rows, generated images) is keyed
# on the internal numeric user.id.


def _find_by_participant_id(db: Session, participant_id: str) -> models.User | None:
    """Case-insensitive lookup so 'Sara' and 'sara' can't be confused."""
    return (
        db.query(models.User)
        .filter(func.lower(models.User.participant_code) == participant_id.lower())
        .first()
    )


# ─────────────────────────────
# SIGNUP (anonymous, user-chosen ID)
# ─────────────────────────────
def _assign_group(db: Session) -> str:
    """Assign the between-subjects arm, balanced as the study fills up.

    Not a plain coin flip: with the small samples a study like this recruits,
    independent flips drift easily (20 participants can land 13/7 without
    anything being wrong). This counts the existing arms and assigns the
    smaller one, breaking ties randomly, so the groups stay close to even at
    every point during recruitment rather than only in expectation.

    EFT_GROUP_RATIO shifts the target away from 50/50 if a design needs it.
    """
    eft = db.query(models.User).filter(models.User.study_group == "eft").count()
    control = (db.query(models.User)
               .filter(models.User.study_group == "control").count())
    total = eft + control
    if total == 0:
        return "eft" if random.random() < EFT_GROUP_RATIO else "control"

    # Whichever arm is behind its target share gets the next participant.
    # Randomising only on an exact tie keeps the arms within one of each
    # other at every point, instead of merely even in expectation — an
    # earlier tolerance-based version fell back to a coin flip almost every
    # time and produced 6/4 over ten signups.
    share = eft / total
    if share < EFT_GROUP_RATIO:
        return "eft"
    if share > EFT_GROUP_RATIO:
        return "control"
    return "eft" if random.random() < EFT_GROUP_RATIO else "control"


@router.post("/signup", status_code=status.HTTP_201_CREATED)
def signup(user: UserCreate, db: Session = Depends(get_db)):
    """
    The participant picks any unique ID (they can choose something
    anonymous). Returns a token directly so no second login call is needed.
    """
    if _find_by_participant_id(db, user.participant_id) is not None:
        raise HTTPException(
            status_code=409, detail="This ID is already taken"
        )

    new_user = models.User(
        participant_code=user.participant_id,
        password_hash=hash_password(user.password),
        full_name_fa=(user.first_name or "").strip() or None,
        study_group=_assign_group(db),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    access_token = create_access_token({"sub": new_user.participant_code})
    return {
        "signup_ok": True,
        "participant_id": new_user.participant_code,
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": new_user.id,
            "participant_id": new_user.participant_code,
            "full_name_fa": new_user.full_name_fa,
        },
    }


# ─────────────────────────────
# LOGIN (ID + password)
# ─────────────────────────────
@router.post("/login")
def login(body: UserLogin, db: Session = Depends(get_db)):
    user = _find_by_participant_id(db, body.participant_id)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token({"sub": user.participant_code})
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "participant_id": user.participant_code,
            "full_name_fa": user.full_name_fa,
        },
    }


# ─────────────────────────────
# CURRENT USER
# ─────────────────────────────
@router.get("/me")
def me(current_user: models.User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "participant_id": current_user.participant_code,
        "full_name_fa": current_user.full_name_fa,
        "created_at": current_user.created_at,
    }
