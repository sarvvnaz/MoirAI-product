from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import models
from app.database.db_setup import get_db
from app.services.security import get_current_user
from app.config import NEUTRAL_RATIO, REMINDERS_DIR
from app.services.image_service import (
    generate_reminder,
    generate_reminder_set,
    create_placeholder_reminder,
    generic_reminders,
    FALLBACK_CUE,
)

router = APIRouter(prefix="/api/extension", tags=["Extension"])

# In-memory set of users currently in an active study session. The extension
# gates its overlay on THIS (fetched from the backend) rather than on a
# website→extension message, so tab-switch reminders don't depend on the
# extension ID or message delivery. Single-process study server → fine;
# ephemeral by design (a restart just means no session is active).
_ACTIVE_STUDY_USERS: set[int] = set()


def default_image_url_for_user(user_id: int) -> str:
    return f"https://picsum.photos/seed/moirai-user-{user_id}/900/600"


@router.post("/session")
def set_session_active(
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Marks the current user's study session active/inactive. The extension
    reads this to decide whether to show reminders on tab switches."""
    active = bool((data or {}).get("active", False))
    if active:
        _ACTIVE_STUDY_USERS.add(current_user.id)
    else:
        _ACTIVE_STUDY_USERS.discard(current_user.id)
    return {"ok": True, "study_active": active}


@router.get("/status")
def extension_status(
    current_user: models.User = Depends(get_current_user),
):
    """Lightweight poll for the extension: is a study session active for this
    (token's) user right now?"""
    return {
        "ok": True,
        "user_id": current_user.id,
        "study_active": current_user.id in _ACTIVE_STUDY_USERS,
    }


def _is_generated(reminder: models.ExtensionReminder | None) -> bool:
    return reminder is not None and _file_exists(reminder.image_url)


def _file_exists(image_url: str | None) -> bool:
    """Is there actually a file behind this /static/reminders/... URL?

    The database row and the image file live in different places — the row is
    in Postgres, the file on the container's disk — so a redeploy can leave a
    row pointing at a file that no longer exists. The row alone then reports
    "ready" while the extension fetches 404 after 404 and the participant sees
    nothing, with the study looking healthy from the server's side.

    Checking the file makes a lost image look like no image, so the pipeline
    regenerates it instead of serving a dead URL forever.
    """
    if not image_url or not image_url.startswith("/static/reminders/"):
        return False
    name = image_url.split("/static/reminders/", 1)[1].split("?", 1)[0]
    if not name or "/" in name or ".." in name:
        return False
    path = REMINDERS_DIR / name
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


@router.post("/ensure-reminder")
def ensure_reminder(
    data: dict | None = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    Ensures the user has a personalized reminder (AI image + cue) generated
    from their confirmed EFT episode. Idempotent: if a generated reminder
    already exists it is returned as-is, unless `{"regenerate": true}` is
    passed in the body.
    """
    regenerate = bool((data or {}).get("regenerate", False))
    # Work step 8 debugging: {"placeholder": true} stores a placeholder image
    # under the user's id — tests the full pipeline without OpenAI cost.
    placeholder = bool((data or {}).get("placeholder", False))
    # Work step 10: {"generate_set": true} → 3 real images + cues.
    generate_set = bool((data or {}).get("generate_set", False))

    reminder = (
        db.query(models.ExtensionReminder)
        .filter(models.ExtensionReminder.user_id == current_user.id)
        .first()
    )

    if generate_set:
        # Debug phase: 1 image per participant (configurable; the real study
        # flow requests 3 for rotation without repetition).
        count = int((data or {}).get("count", 1))
        existing = (
            db.query(models.ReminderAsset)
            .filter(models.ReminderAsset.user_id == current_user.id)
            .count()
        )
        if existing >= count and not regenerate:
            assets = (
                db.query(models.ReminderAsset)
                .filter(models.ReminderAsset.user_id == current_user.id)
                .order_by(models.ReminderAsset.asset_index)
                .all()
            )
        else:
            assets = generate_reminder_set(db, current_user, count=count)
        return {
            "ok": True,
            "user_id": current_user.id,
            "generated": len(assets) > 0,
            "assets": [
                {"index": a.asset_index, "image_url": a.image_url, "cue": a.cue}
                for a in assets
            ],
        }

    if placeholder:
        reminder = create_placeholder_reminder(db, current_user)
        generated = _is_generated(reminder)
    elif _is_generated(reminder) and not regenerate:
        generated = True
    else:
        reminder = generate_reminder(db, current_user)
        generated = _is_generated(reminder)

    return {
        "ok": True,
        "user_id": current_user.id,
        "image_url": reminder.image_url,
        "cue": reminder.cue,
        "generated": generated,
    }


@router.get("/reminder-status")
def reminder_status(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Does this participant have something to be shown during a session?

    The frontend blocks entry to a study session on this: a session run with no
    reminder is a session with no intervention, which is unusable as data and
    indistinguishable afterwards from one that simply didn't work.

    What counts as "ready" depends on the arm, because the arms are waiting
    for different things. The eft arm needs its own generated image. The
    control arm is never given one, so asking it to wait for a personalized
    image would block it forever — for control, ready means the shared
    generic set is installed.

    For the eft arm `ready` reuses the same test as the rest of this router
    (_is_generated → image_url starts with '/static/'), because a placeholder
    row can exist long before any image does — so "a reminder row exists" is
    NOT the same question as "an image was generated".
    """
    if (current_user.study_group or "eft") == "control":
        generic = generic_reminders()
        return {
            "ok": True,
            "ready": bool(generic),
            "count": len(generic),
            "image_url": generic[0]["image_url"] if generic else None,
            "is_generic": True,
            "study_group": "control",
        }

    assets = (
        db.query(models.ReminderAsset)
        .filter(models.ReminderAsset.user_id == current_user.id)
        .order_by(models.ReminderAsset.asset_index)
        .all()
    )
    # The FILE must exist, not merely the row — see _file_exists.
    real = [a for a in assets if _file_exists(a.image_url)]
    if real:
        return {
            "ok": True,
            "ready": True,
            "count": len(real),
            "image_url": real[0].image_url,
            # ReminderAsset has no is_generic column yet — it arrives with the
            # generic-vs-personalized condition arm. getattr keeps this
            # endpoint's shape stable now and correct the moment it lands.
            "is_generic": bool(getattr(real[0], "is_generic", False)),
        }

    reminder = (
        db.query(models.ExtensionReminder)
        .filter(models.ExtensionReminder.user_id == current_user.id)
        .first()
    )
    if _is_generated(reminder):
        return {
            "ok": True,
            "ready": True,
            "count": 1,
            "image_url": reminder.image_url,
            "is_generic": False,
        }

    return {
        "ok": True,
        "ready": False,
        "count": 0,
        "image_url": reminder.image_url if reminder else None,
        "is_generic": False,
    }


@router.get("/reminder-set")
def reminder_set(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """Everything the extension needs to run the two-condition design.

    Returns BOTH arms plus the probability, so the client can render either
    one instantly at trigger time without a network round-trip — overlays are
    prefetched deliberately, and adding a request before each would put a
    visible delay between the disengagement and the reminder.

    `generic_ratio` is served rather than hard-coded in the extension so the
    split can be changed centrally, without asking participants to reinstall.
    Which arm was actually shown is reported back by the client on
    /api/research/event/reminder-shown — the shown condition has to come from
    whatever did the rendering, not from a second independent roll here.
    """
    assets = (
        db.query(models.ReminderAsset)
        .filter(models.ReminderAsset.user_id == current_user.id)
        .filter(models.ReminderAsset.is_generic == False)  # noqa: E712
        .order_by(models.ReminderAsset.asset_index)
        .all()
    )
    personalized = [
        {"index": a.asset_index, "image_url": a.image_url, "cue": a.cue}
        for a in assets
    ]

    if not personalized:
        reminder = (
            db.query(models.ExtensionReminder)
            .filter(models.ExtensionReminder.user_id == current_user.id)
            .first()
        )
        if reminder is not None:
            personalized = [{"index": 0, "image_url": reminder.image_url,
                             "cue": reminder.cue}]

    generic = generic_reminders()
    group = current_user.study_group or "eft"

    if group == "control":
        # The control arm never sees a personalized image, whatever happens to
        # exist in the database for them. Sending it and trusting the client
        # not to show it would put the study's validity in the extension's
        # hands; withholding it here makes that impossible.
        return {
            "ok": True,
            "study_group": group,
            "assets": generic,
            "personalized": [],
            "generic": generic,
            "generic_ratio": 1.0,
        }

    # The eft arm never sees a generic image. Mirror of the control branch
    # above: the generic set is withheld entirely rather than sent with a
    # ratio of 0, because anything shipped to the client can be shown by it.
    #
    # This used to send NEUTRAL_RATIO, a leftover from the earlier
    # within-participant design. With NEUTRAL_RATIO=0.5 on the server that
    # meant personalized participants saw the control image on roughly half
    # their triggers — the arms were not separated at all, and the data would
    # have looked like a valid between-subjects study while being neither.
    return {
        "ok": True,
        "study_group": group,
        # Kept for older installed extensions, which read `assets` and know
        # nothing about conditions. They keep showing the personalized arm.
        "assets": personalized,
        "personalized": personalized,
        "generic": [],
        "generic_ratio": 0.0,
    }


@router.get("/active-reminder")
def active_reminder(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    reminder = (
        db.query(models.ExtensionReminder)
        .filter(models.ExtensionReminder.user_id == current_user.id)
        .first()
    )

    if reminder is None:
        # Fallback so the extension always has something to show; the real
        # personalized reminder is created via /ensure-reminder.
        reminder = models.ExtensionReminder(
            user_id=current_user.id,
            image_url=default_image_url_for_user(current_user.id),
            cue=FALLBACK_CUE,
        )
        db.add(reminder)
        db.commit()
        db.refresh(reminder)

    return {
        "ok": True,
        "user_id": current_user.id,
        "participant_code": current_user.participant_code,
        "image_url": reminder.image_url,
        "cue": reminder.cue,
        "generated": (reminder.image_url or "").startswith("/static/"),
    }


@router.get("/debug/generate-image/{user_id}", summary="Debug generate reminder image")
def debug_generate_image(
    user_id: int,
    db: Session = Depends(get_db),
):
    """DEBUG only: generate a single reminder image + cue for the given
    user id and return the resulting reminder. This endpoint is intentionally
    unauthenticated for debugging; remove or secure it before production use.
    """
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        return {"ok": False, "error": "user not found"}

    # Reuse the existing pipeline which updates DB and returns a reminder.
    reminder = generate_reminder(db, user)
    return {
        "ok": True,
        "user_id": user_id,
        "image_url": reminder.image_url,
        "cue": reminder.cue,
        "generated": (reminder.image_url or "").startswith("/static/"),
    }
