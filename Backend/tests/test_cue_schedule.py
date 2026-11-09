"""The scheduled-cue protocol.

What these protect, in order of how badly a regression would hurt:

  1. EXACTLY TWO cues per participant. Equal dosage across arms is the claim
     the whole redesign rests on; a double-granted slot silently breaks it.
  2. The two primary measures land on the right rows. Return latency is only
     meaningful for a cue shown to someone who had already left; retention
     only for one shown to someone who was present. Pooling them would
     average two different questions.
  3. The arm decides the condition, never the client.
"""
from __future__ import annotations

from datetime import timedelta

from app.config import CUE_GRACE_SECONDS, CUE_OFFSETS_SECONDS
from app.database import models
from app.routers import cues


def _rewind(db, session, seconds: float):
    """Pretend the reading window opened `seconds` ago.

    Cheaper and far more reliable than sleeping for ten minutes, and it lets
    a test sit exactly on a boundary.
    """
    session.reading_started_at = cues._utcnow() - timedelta(seconds=seconds)
    db.commit()


def _start(client, user, session_for):
    session_for(user)
    client.login(user)
    r = client.post("/api/study/session/start-reading")
    assert r.status_code == 201, r.text
    return r


# ── scheduling ────────────────────────────────────────────────────────
def test_start_reading_creates_one_row_per_slot(client, db, make_user,
                                                session_for, assets_for):
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    rows = db.query(models.CueDelivery).all()
    assert [r.slot for r in rows] == [1, 2]
    # Created up front and undelivered: an absent delivery must be visible as
    # a NULL, not as a missing row.
    assert all(r.delivered_at is None for r in rows)


def test_start_reading_is_idempotent(client, db, make_user, session_for,
                                     assets_for):
    """A page reload must not restart the clock or hand out extra cues."""
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)
    first = db.query(models.Session).first().reading_started_at

    r = client.post("/api/study/session/start-reading")
    assert r.json()["already_started"] is True
    assert db.query(models.CueDelivery).count() == 2
    assert db.query(models.Session).first().reading_started_at == first


def test_no_slot_due_before_first_offset(client, db, make_user, session_for,
                                         assets_for):
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    _rewind(db, db.query(models.Session).first(), CUE_OFFSETS_SECONDS[0] - 5)
    assert client.get("/api/study/cue/due").json()["due_slot"] is None


def test_slot_due_inside_window(client, db, make_user, session_for, assets_for):
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    _rewind(db, db.query(models.Session).first(), CUE_OFFSETS_SECONDS[0] + 1)
    assert client.get("/api/study/cue/due").json()["due_slot"] == 1


def test_claim_before_due_is_refused(client, db, make_user, session_for,
                                     assets_for):
    """A tab switch on its own no longer shows anything — that is the change."""
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    _rewind(db, db.query(models.Session).first(), 30)
    r = client.post("/api/study/cue/claim",
                    json={"state": "off_tab", "claimed_by": "extension"})
    assert r.json() == {"granted": False, "reason": "no_slot_due"}


# ── the dosage guarantee ──────────────────────────────────────────────
def test_slot_is_granted_exactly_once(client, db, make_user, session_for,
                                      assets_for):
    """Both clients race for every slot; only one may win."""
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)
    _rewind(db, db.query(models.Session).first(), CUE_OFFSETS_SECONDS[0] + 1)

    first = client.post("/api/study/cue/claim",
                        json={"state": "active", "claimed_by": "app"}).json()
    second = client.post("/api/study/cue/claim",
                         json={"state": "off_tab",
                               "claimed_by": "extension"}).json()

    assert first["granted"] is True
    assert second == {"granted": False, "reason": "already_claimed"}


def test_grace_expiry_records_a_reason(client, db, make_user, session_for,
                                       assets_for):
    """An undelivered cue must never look like a cue that was never due."""
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    _rewind(db, db.query(models.Session).first(),
            CUE_OFFSETS_SECONDS[0] + CUE_GRACE_SECONDS + 1)
    client.get("/api/study/cue/due")

    slot1 = db.query(models.CueDelivery).filter_by(slot=1).first()
    assert slot1.delivered_at is None
    assert slot1.not_delivered_reason == "grace_expired"


def test_missing_assets_are_flagged_not_silent(client, db, make_user,
                                               session_for, assets_for):
    """A participant with one asset still walks the protocol; slot 2 must say
    why it produced nothing rather than looking like an ignored cue."""
    user = make_user()
    assets_for(user, count=1)
    _start(client, user, session_for)

    slot2 = db.query(models.CueDelivery).filter_by(slot=2).first()
    assert slot2.not_delivered_reason == "no_asset_available"


# ── state → form, and the arm → condition ─────────────────────────────
def test_state_selects_form(client, db, make_user, session_for, assets_for):
    for state, form in [("active", "corner_card"),
                        ("idle", "in_app_overlay"),
                        ("off_tab", "full_page_modal"),
                        ("off_browser", "full_page_modal")]:
        user = make_user(code=f"P-{state}")
        assets_for(user)
        _start(client, user, session_for)
        _rewind(db, db.query(models.Session)
                .filter_by(user_id=user.id).first(),
                CUE_OFFSETS_SECONDS[0] + 1)

        r = client.post("/api/study/cue/claim",
                        json={"state": state, "claimed_by": "app"}).json()
        assert r["form"] == form, state


def test_condition_follows_the_arm_not_the_client(client, db, make_user,
                                                  session_for, assets_for):
    """The client reports the state it can observe; it never names its own
    condition. A stale build must not be able to move a participant between
    arms in the data."""
    control = make_user(study_group="control", code="C1")
    _start(client, control, session_for)
    _rewind(db, db.query(models.Session).first(), CUE_OFFSETS_SECONDS[0] + 1)

    r = client.post("/api/study/cue/claim",
                    json={"state": "off_tab", "claimed_by": "extension",
                          "condition": "personalized"}).json()
    assert r.get("condition") in (None, "neutral")
    row = db.query(models.CueDelivery).filter_by(slot=1).first()
    assert row.condition == "neutral"


def test_claim_rejects_unknown_state(client, db, make_user, session_for,
                                     assets_for):
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)
    r = client.post("/api/study/cue/claim",
                    json={"state": "distracted", "claimed_by": "app"})
    assert r.status_code == 422


# ── delivery audit ────────────────────────────────────────────────────
def test_shown_records_how_late_the_cue_was(client, db, make_user,
                                            session_for, assets_for):
    """chrome.alarms has a 30s floor, so 'fired at minute 10' is a claim the
    data has to be able to check."""
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)
    _rewind(db, db.query(models.Session).first(), CUE_OFFSETS_SECONDS[0] + 12)

    delivery_id = client.post(
        "/api/study/cue/claim",
        json={"state": "active", "claimed_by": "app"}).json()["delivery_id"]
    client.post(f"/api/study/cue/{delivery_id}/shown")

    row = db.query(models.CueDelivery).get(delivery_id)
    assert row.delivered_at is not None
    assert 10_000 <= row.delivery_offset_ms <= 20_000
    assert row.not_delivered_reason is None


def test_early_finish_marks_the_undelivered_slot(client, db, make_user,
                                                 session_for, assets_for):
    """Someone who finishes at minute 12 never reaches slot 2.

    That is under-dosage, not a delivery failure, and the two must stay
    distinguishable: this row broke the equal-exposure assumption the whole
    design rests on, and it has to be visible rather than inferred from a NULL.
    """
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)
    _rewind(db, db.query(models.Session).first(), CUE_OFFSETS_SECONDS[0] + 1)

    _claim = client.post("/api/study/cue/claim",
                         json={"state": "active", "claimed_by": "app"}).json()
    client.post(f"/api/study/cue/{_claim['delivery_id']}/shown")

    client.post("/api/study/session/end-reading")

    slot2 = db.query(models.CueDelivery).filter_by(slot=2).first()
    assert slot2.delivered_at is None
    assert slot2.not_delivered_reason == "session_ended_before_slot"

    # Slot 1 genuinely delivered and must not be relabelled.
    slot1 = db.query(models.CueDelivery).filter_by(slot=1).first()
    assert slot1.delivered_at is not None
    assert slot1.not_delivered_reason is None


def test_grace_expiry_and_early_finish_are_different_reasons(
        client, db, make_user, session_for, assets_for):
    """Both leave delivered_at NULL, and they mean opposite things: one is a
    delivery bug to fix, the other is a participant who finished early."""
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    # Slot 1's window opened and closed with nothing delivered.
    _rewind(db, db.query(models.Session).first(),
            CUE_OFFSETS_SECONDS[0] + CUE_GRACE_SECONDS + 1)
    client.get("/api/study/cue/due")
    client.post("/api/study/session/end-reading")

    reasons = {r.slot: r.not_delivered_reason
               for r in db.query(models.CueDelivery).all()}
    assert reasons[1] == "grace_expired"
    assert reasons[2] == "session_ended_before_slot"


# ── overlapping grace windows ─────────────────────────────────────────
def test_short_offsets_still_deliver_both_slots(client, db, make_user,
                                                session_for, assets_for,
                                                monkeypatch):
    """Shortening the offsets to test the protocol must not break it.

    With offsets 60s apart and a 90s grace, slot 1's window used to swallow
    slot 2's opening. The scan found slot 1, saw it was already delivered, and
    refused — so the second cue never fired and nothing recorded a failure.
    Production offsets are 600s apart, so this only appeared to whoever
    shortened them to avoid waiting twenty minutes.
    """
    monkeypatch.setattr(cues, "CUE_OFFSETS_SECONDS", [60, 120])
    user = make_user()
    assets_for(user)
    _start(client, user, session_for)

    _rewind(db, db.query(models.Session).first(), 62)
    first = client.post("/api/study/cue/claim",
                        json={"state": "active", "claimed_by": "app"}).json()
    assert first["granted"] is True and first["slot"] == 1

    _rewind(db, db.query(models.Session).first(), 122)
    second = client.post("/api/study/cue/claim",
                         json={"state": "off_tab",
                               "claimed_by": "extension"}).json()
    assert second["granted"] is True, second
    assert second["slot"] == 2


def test_grace_never_reaches_the_next_slot(monkeypatch):
    """The invariant behind the bug above, checked directly."""
    for offsets in ([60, 120], [600, 1200], [30, 45]):
        monkeypatch.setattr(cues, "CUE_OFFSETS_SECONDS", offsets)
        for i in range(1, len(offsets)):
            end = offsets[i - 1] + cues._effective_grace(i)
            assert end <= offsets[i], (offsets, i)


def test_the_later_slot_wins_if_windows_ever_overlap(monkeypatch):
    """Belt and braces: an exhausted earlier window must never mask a newer
    cue, because the newer one is the cue that should actually be shown."""
    monkeypatch.setattr(cues, "CUE_OFFSETS_SECONDS", [60, 120])
    assert cues._slot_due(122) == 2
    assert cues._slot_due(62) == 1
