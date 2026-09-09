"""The measurement battery: serving items and recording answers.

The item bank lives on the SERVER (app/measure_items.py), not in the
Flutter app, for two reasons. The battery is study design and changes during
piloting, and reissuing it must not mean asking participants to reload a new
build. And which items a participant sees depends on their arm — a decision
that belongs where the arm is stored, not in a client that could be wrong.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import measure_items
from app.database import models
from app.database.db_setup import get_db
from app.services.security import get_current_user

router = APIRouter(prefix="/api/measures", tags=["Measures"])

VALID_TIMEPOINTS = set(measure_items.TIMEPOINTS)


@router.get("/items")
def get_items(
    timepoint: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Items due at this timepoint for this participant's arm.

    An empty list is a normal answer, not an error: the control arm has
    nothing at post_chat, and the client is expected to skip the page rather
    than show an empty form.
    """
    if timepoint not in VALID_TIMEPOINTS:
        raise HTTPException(status_code=422, detail=f"unknown timepoint {timepoint!r}")

    items = measure_items.items_for(timepoint, current_user.study_group)

    answered = {
        r.item_code
        for r in db.query(models.MeasureResponse)
        .filter(models.MeasureResponse.user_id == current_user.id,
                models.MeasureResponse.timepoint == timepoint)
        .all()
    }

    return {
        "ok": True,
        "timepoint": timepoint,
        "study_group": current_user.study_group or "eft",
        "already_answered": sorted(answered),
        "items": [
            {
                "code": i["code"],
                "instrument": i["instrument"],
                "text_fa": i["text_fa"],
                "scale": i["scale"],
            }
            for i in items
        ],
    }


@router.post("/responses", status_code=status.HTTP_200_OK)
def save_responses(
    data: dict,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Record answers for one timepoint.

    Body: {"timepoint": "baseline", "responses": {"fsc_similarity": 4, ...}}

    Upserts on (user, item, timepoint) so a participant who goes back and
    resubmits corrects their answer instead of leaving two contradictory rows
    for the same question.

    reverse and scale_max are copied onto each row rather than looked up later:
    the item bank will change during piloting, and a stored response has to
    stay interpretable without knowing which version of the bank produced it.
    """
    timepoint = (data or {}).get("timepoint")
    if timepoint not in VALID_TIMEPOINTS:
        raise HTTPException(status_code=422, detail=f"unknown timepoint {timepoint!r}")

    responses = (data or {}).get("responses") or {}
    if not isinstance(responses, dict):
        raise HTTPException(status_code=422, detail="responses must be an object")

    by_code = {i["code"]: i
               for i in measure_items.items_for(timepoint, current_user.study_group)}

    saved, ignored = 0, []
    for code, raw in responses.items():
        item = by_code.get(code)
        if item is None:
            # Not an error worth failing the whole submission for — but it
            # must not be stored silently either, or a client sending stale
            # item codes would look like it was working.
            ignored.append(code)
            continue

        value, text_value = None, None
        if isinstance(raw, str):
            text_value = raw.strip() or None
        elif raw is not None:
            try:
                value = int(raw)
            except (TypeError, ValueError):
                ignored.append(code)
                continue

        row = (
            db.query(models.MeasureResponse)
            .filter(models.MeasureResponse.user_id == current_user.id,
                    models.MeasureResponse.item_code == code,
                    models.MeasureResponse.timepoint == timepoint)
            .first()
        )
        if row is None:
            row = models.MeasureResponse(
                user_id=current_user.id, item_code=code, timepoint=timepoint)
            db.add(row)

        scale = item["scale"]
        row.instrument = item["instrument"]
        row.value = value
        row.text_value = text_value
        row.reverse = bool(item.get("reverse"))
        # Choice items carry no explicit max, so derive it from the option
        # count — otherwise a stored 3 gives no clue whether the scale ran to
        # 5 or to 7, and the row stops being self-interpreting.
        row.scale_max = scale.get("max") or len(scale.get("options_fa") or []) or None
        saved += 1

    db.commit()
    if ignored:
        print(f"⚠️ measures: ignored unknown/unparsable items at {timepoint} "
              f"for user {current_user.id}: {ignored}")
    return {"ok": True, "timepoint": timepoint, "saved": saved,
            "ignored": ignored}
