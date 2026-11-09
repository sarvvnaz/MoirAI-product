# eft.py
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import measure_items
from app.database import models
from app.database.db_setup import get_db
from app.services.eft_chat_service_v2 import (
    EFTChatServiceV2,
    IMPORTANCE_KEY,
    QUESTIONS as CHAT_QUESTIONS,
)
from app.services.security import get_current_user

router = APIRouter(prefix="/api/eft", tags=["EFT"])

# ----------------------------------------------------------------------------
# Episode lock: the participant builds their episode EITHER through the chat
# OR through the manual form — never both. Whichever one is SUBMITTED first
# locks the other out permanently (stored as `_locked_by` in the chat state,
# so no schema migration is needed).
# ----------------------------------------------------------------------------
EPISODE_KEYS = [q["key"] for q in CHAT_QUESTIONS]


def _get_chat_state(db: Session, user_id: int) -> models.EFTChatState | None:
    return (
        db.query(models.EFTChatState)
        .filter(models.EFTChatState.user_id == user_id)
        .first()
    )


def _state_fields(state: models.EFTChatState | None) -> dict:
    if state is None:
        return {}
    try:
        return json.loads(state.fields_json or "{}")
    except Exception:
        return {}


def _locked_by(state: models.EFTChatState | None) -> str | None:
    """Returns 'chat', 'manual', or None (nothing submitted yet)."""
    value = _state_fields(state).get("_locked_by")
    return value if value in ("chat", "manual") else None


def _mark_locked(db: Session, user_id: int, source: str) -> None:
    """Stamps the winning submission path onto the chat state."""
    state = _get_chat_state(db, user_id)
    if state is None:
        state = models.EFTChatState(
            user_id=user_id, current_step=0, fields_json="{}")
        db.add(state)
        db.flush()
    fields = _state_fields(state)
    if fields.get("_locked_by") in ("chat", "manual"):
        return  # first submission wins; never overwrite
    fields["_locked_by"] = source
    state.fields_json = json.dumps(fields, ensure_ascii=False)
    state.last_updated = datetime.utcnow()


def _manual_locked_result(state: models.EFTChatState | None) -> dict:
    """The chat's reply shape, for a participant who already submitted the
    manual form: nothing to answer, ready to continue."""
    fields = _state_fields(state)
    summary = fields.get("_summary") or ""
    return {
        "bot": ("تو پاسخ‌هات رو از راه فرم دستی ثبت کردی ✅\n\n"
                f"{summary}\n\n"
                "برای ادامه، دکمه‌ی «ادامه» رو بزن.").strip(),
        "needs_user": False,
        "can_start_session": True,
        "question_index": len(CHAT_QUESTIONS),
        "collected": [bool(fields.get(k)) for k in EPISODE_KEYS],
        "episode_summary": summary or None,
        "locked_by": "manual",
    }


@router.get("/lock-status", status_code=status.HTTP_200_OK)
def eft_lock_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Which path (if any) the participant has already submitted with. The
    frontend uses this to disable the manual form after a chat submission,
    and to block returning to the chat after a manual submission."""
    return {"ok": True, "locked_by": _locked_by(_get_chat_state(db, current_user.id))}


@router.post("/manual", status_code=status.HTTP_200_OK)
def submit_manual_episode(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Manual fallback for when the chat fails the participant: the same 7
    questions answered in plain text boxes. Writes the same EFTEpisode row
    the chat writes, so image generation is completely unaffected."""
    state = _get_chat_state(db, current_user.id)
    if _locked_by(state) == "chat":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Episode already submitted through the chat.",
        )

    answers = data.get("answers") or {}
    cleaned = {k: str(answers.get(k) or "").strip() for k in EPISODE_KEYS}
    missing = [k for k, v in cleaned.items() if not v]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing answers: {', '.join(missing)}",
        )

    summary = "\n".join(
        f"• {q['short']}: {cleaned[q['key']]}" for q in CHAT_QUESTIONS)

    if state is None:
        state = models.EFTChatState(
            user_id=current_user.id, current_step=0, fields_json="{}")
        db.add(state)
        db.flush()
    fields = _state_fields(state)
    fields.update(cleaned)
    fields["_summary"] = summary
    fields["_locked_by"] = "manual"
    state.fields_json = json.dumps(fields, ensure_ascii=False)
    state.current_step = len(CHAT_QUESTIONS)
    state.last_updated = datetime.utcnow()

    episode = dict(cleaned)
    episode["_summary"] = summary
    episode["_source"] = "manual"
    db.add(models.EFTEpisode(
        user_id=current_user.id,
        episode_json=json.dumps(episode, ensure_ascii=False),
    ))

    db.commit()
    return {"ok": True, "locked_by": "manual", "summary": summary}

# ----------------------------------------------------------------------------
# New endpoint: save structured episode
# ----------------------------------------------------------------------------
@router.post("/episode", status_code=status.HTTP_201_CREATED)
def save_eft_episode(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Saves a structured EFT episode for the current user. The request body
    should include an `episode` field containing the episode JSON object.

    Example request body:
      {
        "episode": {
          ... as defined in the frontend episode schema ...
        }
      }

    The episode is stored as a JSON string in the EFTEpisode table.
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    episode_data = data.get("episode")
    if episode_data is None:
        raise HTTPException(status_code=422, detail="Missing episode data")

    try:
        # Serialise to JSON string to persist
        import json as _json
        episode_json_str = _json.dumps(episode_data, ensure_ascii=False)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid episode JSON: {e}")

    episode = models.EFTEpisode(
        user_id=current_user.id,
        episode_json=episode_json_str,
    )
    db.add(episode)
    db.commit()
    db.refresh(episode)

    return {"ok": True, "episode_id": episode.id}


# ----------------------------------------------------------------------------
# Backend-driven EFT chat
# ----------------------------------------------------------------------------
@router.post("/chat", status_code=status.HTTP_200_OK)
def eft_chat(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    message = data.get("message")
    reset = bool(data.get("reset", False))

    # Importance is a 1-6 chip tap, not a typed message, so it arrives on its
    # own field. Anything unparseable is ignored rather than 422'd — a bad
    # rating must never be able to wedge a participant mid-study.
    importance = data.get("importance")
    if importance is not None:
        try:
            importance = int(importance)
        except (TypeError, ValueError):
            importance = None

    # Manual submission already locked the episode — the chat is closed for
    # good (checked BEFORE any reset, which would otherwise wipe the answers).
    state = _get_chat_state(db, current_user.id)
    if _locked_by(state) == "manual":
        return _manual_locked_result(state)

    if not reset:
        _seed_goal_from_future_goal(db, current_user)

    service = EFTChatServiceV2(db, current_user.id)
    result = service.process_message(message, reset=reset, importance=importance)

    # On final confirmation, persist the episode server-side so research data
    # is never lost even if the frontend drops the /episode call. Save only
    # the 7 clean question keys (not chat history/bookkeeping).
    if result.get("can_start_session"):
        has_episode = (
            db.query(models.EFTEpisode)
            .filter(models.EFTEpisode.user_id == current_user.id)
            .first()
        )
        if has_episode is None:
            state = _get_chat_state(db, current_user.id)
            if state is not None:
                fields = _state_fields(state)
                episode = {q["key"]: fields.get(q["key"])
                           for q in CHAT_QUESTIONS}
                # 1-6 rating of how much the distal goal matters. Research
                # data in its own right (importance predicts EFT effect), so
                # it goes into the episode rather than staying in chat state,
                # which is transient.
                episode[IMPORTANCE_KEY] = fields.get(IMPORTANCE_KEY)
                episode["_summary"] = fields.get("_summary")
                episode["_source"] = "chat"
                db.add(models.EFTEpisode(
                    user_id=current_user.id,
                    episode_json=json.dumps(episode, ensure_ascii=False),
                ))
                # MIRROR the importance rating into the measurement table.
                #
                # The chatbot already asks it at the right moment — straight
                # after the goal, before the episodic detail questions — so
                # nothing about the chat needs changing. But the control arm
                # answers the SAME item through the questionnaire layer, and
                # if the EFT arm's copy lived only inside episode_json the two
                # arms' answers would sit in different places, in different
                # shapes, and could not be compared without special-casing the
                # export.
                #
                # Written with the item bank's own provenance so the mirrored
                # row is indistinguishable from a directly-answered one.
                _mirror_goal_importance(
                    db, current_user, fields.get(IMPORTANCE_KEY))
        # Chat won the race → the manual form is closed from now on.
        _mark_locked(db, current_user.id, "chat")

    db.commit()
    return result


def _mirror_goal_importance(db: Session, user, value) -> None:
    """Record the chatbot's importance rating as the shared goal_importance
    item, so both conditions' answers land in one comparable place.

    Idempotent: re-running the episode save must not create a second row.
    """
    if value is None:
        return
    # goal_importance is NOT part of the active questionnaire battery in this
    # version — the chatbot asks it, nothing else does. So its metadata is
    # spelled out here rather than looked up: relying on the battery would
    # make this silently no-op the moment the item left it, and the rating
    # would vanish from the export with nothing to show it had ever been
    # collected.
    item = measure_items.item_by_code("goal_importance") or {
        "instrument": "goal_importance",
        "phase": 3,
        "validated": False,
        "measure_status": measure_items.PUBLISHED_ADAPTED,
        "battery_version": measure_items.BATTERY_VERSION,
        "source": ("Goal-importance construct adapted from Asayama et al. "
                   "(2024); wording is the EFT chatbot's own. Collected "
                   "inside the conversation, not in the battery."),
        "scale_min": 1,
        "scale_max": 6,
    }

    row = (
        db.query(models.MeasureResponse)
        .filter(models.MeasureResponse.user_id == user.id,
                models.MeasureResponse.item_code == "goal_importance",
                models.MeasureResponse.timepoint == "goal_importance")
        .first()
    )
    if row is None:
        row = models.MeasureResponse(
            user_id=user.id, item_code="goal_importance",
            timepoint="goal_importance",
            # instrument is NOT NULL, so it has to be set before the flush
            # below rather than with the rest of the fields.
            instrument=item["instrument"])
        db.add(row)
        # Flushed immediately: the session runs with autoflush off, so a
        # second call in the same transaction would not see this pending row
        # and would add a duplicate — which the unique constraint then turns
        # into an IntegrityError that fails the whole episode save.
        db.flush()

    row.instrument = item["instrument"]
    row.phase = item["phase"]
    row.value = int(value)
    row.validated = bool(item["validated"])
    row.measure_status = item["measure_status"]
    row.battery_version = item["battery_version"]
    row.source = item["source"]
    row.scale_min = item["scale_min"]
    row.scale_max = item["scale_max"]


def _seed_goal_from_future_goal(db: Session, user) -> None:
    """Pre-fill the chatbot's `goal` step with the goal already collected.

    The participant writes their future goal on its own screen, before the
    pre-questionnaire, because the instrumentality items ask about "this
    future goal" and need a referent. Asking for it AGAIN as the chatbot's
    first question would produce two goals per participant with nothing
    saying which one the generated future is about.

    Seeding is done here, in the router, rather than inside the chat service:
    the service's turn logic, probing, extraction and step progression are all
    untouched. It simply starts at step 1 with `goal` already present — from
    its point of view a participant who answered the first question. The
    importance chip row still fires next, because `_needs_importance` keys off
    a goal existing without a rating.

    Only ever runs when no chat state exists yet, so an in-progress or
    finished conversation is never overwritten.
    """
    existing = (
        db.query(models.EFTChatState)
        .filter(models.EFTChatState.user_id == user.id)
        .first()
    )
    if existing is not None:
        return

    row = (
        db.query(models.MeasureResponse)
        .filter(models.MeasureResponse.user_id == user.id,
                models.MeasureResponse.item_code == "future_goal")
        .first()
    )
    goal = (row.text_value or "").strip() if row else ""
    if not goal:
        # No goal on record — let the chatbot ask its own first question, as
        # it always did. Better than starting a conversation about nothing.
        return

    db.add(models.EFTChatState(
        user_id=user.id,
        current_step=1,          # step 0 (`goal`) is already answered
        fields_json=json.dumps({"goal": goal}, ensure_ascii=False),
    ))
    db.flush()


@router.get("/generated-future", status_code=status.HTTP_200_OK)
def generated_future(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """The participant's OWN generated future — image and text.

    Deliberately NOT served from /api/extension/reminder-set. That endpoint
    withholds personalized assets from anyone in the control arm, which is
    correct for the two-arm reminder study it was written for: sending an
    asset and trusting the client not to show it would put that study's
    validity in the extension's hands.

    This version has no control arm — every participant builds a future and
    is shown it — but signup still assigns `study_group`, so roughly half of
    them would reach the visualization screen and be shown the SHARED GENERIC
    image instead of their own. Nothing would error; the demo would just
    quietly display the wrong picture to half the room.

    So this reads the participant's own assets directly, and reminder-set is
    left exactly as it was for the flow that still needs it.
    """
    asset = (
        db.query(models.ReminderAsset)
        .filter(models.ReminderAsset.user_id == current_user.id)
        .filter(models.ReminderAsset.is_generic == False)  # noqa: E712
        .order_by(models.ReminderAsset.asset_index)
        .first()
    )
    if asset is None:
        return {"ok": True, "ready": False, "image_url": None, "cue": None}

    return {
        "ok": True,
        "ready": True,
        "image_url": asset.image_url,
        "cue": asset.cue,
    }


@router.post("/inspire", status_code=status.HTTP_200_OK)
def eft_inspire(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Micro-scenarios for the participant's ACTIVE step, when imagination stalls.

    Returns suggestions only — the frontend drops them into the input box as
    editable text and the participant still has to submit their own version.
    Nothing here touches chat state, so pressing the button repeatedly is free
    and can never advance a step or record an answer the participant did not
    actually give.
    """
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    state = _get_chat_state(db, current_user.id)
    if _locked_by(state) == "manual":
        return {"question_index": 0, "suggestions": []}

    service = EFTChatServiceV2(db, current_user.id)
    return service.inspire()


@router.post("/reset", status_code=status.HTTP_200_OK)
def eft_chat_reset(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if current_user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")

    # A manual submission is final — never let a reset wipe it.
    state = _get_chat_state(db, current_user.id)
    if _locked_by(state) == "manual":
        return _manual_locked_result(state)

    service = EFTChatServiceV2(db, current_user.id)
    result = service.process_message(None, reset=True)
    db.commit()
    return result
