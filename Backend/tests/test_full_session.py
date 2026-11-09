"""One participant, one whole session, both arms.

The unit tests check each endpoint in isolation. This walks the protocol end
to end, because the failures that actually cost a study are the ones between
the parts: a slot delivered but never stamped, an episode left open, a measure
computed against the wrong cue.
"""
from __future__ import annotations

from datetime import timedelta

from app.config import CUE_OFFSETS_SECONDS
from app.database import models
from app.routers import cues
from app.routers.research import _dataset


def _at(db, session, seconds):
    session.reading_started_at = cues._utcnow() - timedelta(seconds=seconds)
    db.commit()


def _shift(db, row, column, seconds):
    setattr(row, column, getattr(row, column) - timedelta(seconds=seconds))
    db.commit()


def _walk(client, db, user, session_for, assets_for):
    """Reads for 10 min, gets the corner card, keeps reading, then leaves at
    minute 20 and is pulled back by the modal."""
    assets_for(user)
    session_for(user)
    client.login(user)
    client.post("/api/study/session/start-reading")
    s = db.query(models.Session).filter_by(user_id=user.id).first()

    # ── minute 10: reading, so the corner card ──
    _at(db, s, CUE_OFFSETS_SECONDS[0] + 2)
    g1 = client.post("/api/study/cue/claim",
                     json={"state": "active", "claimed_by": "app"}).json()
    client.post(f"/api/study/cue/{g1['delivery_id']}/shown")

    # kept reading for 4 minutes, then got distracted
    cue1 = db.query(models.CueDelivery).filter_by(id=g1["delivery_id"]).first()
    _shift(db, cue1, "delivered_at", 240)
    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})
    client.post("/api/study/disengagement/end", json={"ended_by": "return"})

    # ── minute 20: away on another tab, so the modal ──
    _at(db, s, CUE_OFFSETS_SECONDS[1] + 2)
    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})
    ep = (db.query(models.DisengagementEpisode)
          .order_by(models.DisengagementEpisode.id.desc()).first())
    _shift(db, ep, "started_at", 30)

    g2 = client.post("/api/study/cue/claim",
                     json={"state": "off_tab",
                           "claimed_by": "extension"}).json()
    client.post(f"/api/study/cue/{g2['delivery_id']}/shown")
    cue2 = db.query(models.CueDelivery).filter_by(id=g2["delivery_id"]).first()
    _shift(db, cue2, "delivered_at", 6)

    client.post(f"/api/study/cue/{g2['delivery_id']}/interaction",
                json={"clicked_return": True})
    client.post("/api/study/disengagement/end", json={"ended_by": "return"})

    client.post("/api/study/session/end-reading")
    return s


def test_full_session_eft_arm(client, db, make_user, session_for, assets_for):
    user = make_user(study_group="eft")
    _walk(client, db, user, session_for, assets_for)

    cues_rows = (db.query(models.CueDelivery)
                 .order_by(models.CueDelivery.slot).all())

    # DOSAGE: exactly two, both delivered, neither written off.
    assert len(cues_rows) == 2
    assert all(c.delivered_at is not None for c in cues_rows)
    assert all(c.not_delivered_reason is None for c in cues_rows)

    slot1, slot2 = cues_rows

    # Slot 1 reached someone who was reading -> retention only.
    assert slot1.state_at_delivery == "active"
    assert slot1.form == "corner_card"
    assert 235 <= slot1.post_cue_focus_seconds <= 245
    assert slot1.return_latency_ms is None

    # Slot 2 reached someone already away -> latency only.
    assert slot2.state_at_delivery == "off_tab"
    assert slot2.form == "full_page_modal"
    assert 5_500 <= slot2.return_latency_ms <= 6_500
    assert slot2.post_cue_focus_seconds is None
    assert slot2.clicked_return is True

    # The arm, decided server-side throughout.
    assert {c.condition for c in cues_rows} == {"personalized"}

    # Every episode closed, so time-on-task is computable.
    episodes = db.query(models.DisengagementEpisode).all()
    assert len(episodes) == 2
    assert all(e.ended_at is not None and e.duration_ms is not None
               for e in episodes)


def test_full_session_control_arm_is_labelled_neutral(
        client, db, make_user, session_for, assets_for, monkeypatch):
    monkeypatch.setattr(
        cues, "generic_reminders",
        lambda: [{"image_url": "/static/generic/generic_reminder_0.png",
                  "cue": "generic 0"},
                 {"image_url": "/static/generic/generic_reminder_1.png",
                  "cue": "generic 1"}])

    user = make_user(study_group="control", code="C-full")
    _walk(client, db, user, session_for, assets_for)

    rows = db.query(models.CueDelivery).order_by(models.CueDelivery.slot).all()
    assert len(rows) == 2
    assert {c.condition for c in rows} == {"neutral"}
    # Control saw the generic set, and slot order is deterministic.
    assert rows[0].asset_image_url.endswith("generic_reminder_0.png")
    assert rows[1].asset_image_url.endswith("generic_reminder_1.png")


def test_export_carries_the_new_tables(client, db, make_user, session_for,
                                       assets_for):
    """The frozen table stays in the export, alongside the new ones — but the
    two must never be pooled, so both have to be visibly present and separate.
    """
    user = make_user()
    _walk(client, db, user, session_for, assets_for)

    data = _dataset(db)
    assert len(data["cue_deliveries"]) == 2
    assert len(data["disengagement_episodes"]) == 2
    assert data["research_events"] == []  # frozen: nothing written

    row = data["cue_deliveries"][0]
    for field in ("slot", "state_at_delivery", "form", "condition",
                  "delivery_offset_ms", "return_latency_ms",
                  "post_cue_focus_seconds", "not_delivered_reason"):
        assert field in row, f"{field} missing from the export"
