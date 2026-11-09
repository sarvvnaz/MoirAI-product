"""The two primary measures, and the disengagement log they hang off.

The single thing these exist to prevent: return latency and post-cue
retention getting computed for the wrong rows. They answer different
questions —

    return latency  : the cue reached someone who had ALREADY left.
                      "Does it pull them back?"
    retention       : the cue reached someone who was PRESENT.
                      "Does it keep them here?"

— and a row that contributes to the wrong one silently corrupts both, because
neither measure has a plausibility range that would make the mistake visible.
"""
from __future__ import annotations

from datetime import timedelta

from app.config import CUE_OFFSETS_SECONDS
from app.database import models
from app.routers import cues


def _open_window(client, db, user, session_for, assets_for, at=None):
    assets_for(user)
    session_for(user)
    client.login(user)
    client.post("/api/study/session/start-reading")
    s = db.query(models.Session).filter_by(user_id=user.id).first()
    if at is not None:
        s.reading_started_at = cues._utcnow() - timedelta(seconds=at)
        db.commit()
    return s


def _shift(db, row, column, seconds):
    """Move a stored timestamp back, to stand in for elapsed wall-clock."""
    setattr(row, column, getattr(row, column) - timedelta(seconds=seconds))
    db.commit()


def _claim_and_show(client, state):
    d = client.post("/api/study/cue/claim",
                    json={"state": state, "claimed_by": "app"}).json()
    assert d["granted"] is True, d
    client.post(f"/api/study/cue/{d['delivery_id']}/shown")
    return d["delivery_id"]


# ── PRIMARY MEASURE 1: return latency ─────────────────────────────────
def test_return_latency_recorded_for_off_tab_cue(client, db, make_user,
                                                 session_for, assets_for):
    user = make_user()
    _open_window(client, db, user, session_for, assets_for,
                 at=CUE_OFFSETS_SECONDS[0] + 1)

    # Timeline: they left 10s ago, the cue found them 4s ago, they return now.
    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})
    delivery_id = _claim_and_show(client, "off_tab")

    ep = db.query(models.DisengagementEpisode).first()
    _shift(db, ep, "started_at", 10)
    row = db.query(models.CueDelivery).filter_by(id=delivery_id).first()
    _shift(db, row, "delivered_at", 4)

    client.post("/api/study/disengagement/end", json={"ended_by": "return"})

    db.refresh(row)
    assert 3_500 <= row.return_latency_ms <= 5_500
    # A cue shown to someone who was away says nothing about retention.
    assert row.post_cue_focus_seconds is None


def test_no_latency_when_cue_predates_the_absence(client, db, make_user,
                                                  session_for, assets_for):
    """A cue shown BEFORE the participant left did not cause their return.

    Crediting it would measure an interval that begins before the disengagement
    even started — the circularity the whole redesign exists to remove.
    """
    user = make_user()
    _open_window(client, db, user, session_for, assets_for,
                 at=CUE_OFFSETS_SECONDS[0] + 1)

    delivery_id = _claim_and_show(client, "off_tab")
    row = db.query(models.CueDelivery).filter_by(id=delivery_id).first()
    _shift(db, row, "delivered_at", 60)

    # A NEW absence, well after that cue.
    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})
    client.post("/api/study/disengagement/end", json={"ended_by": "return"})

    db.refresh(row)
    assert row.return_latency_ms is None


def test_active_cue_never_gets_a_return_latency(client, db, make_user,
                                                session_for, assets_for):
    """The participant was reading when it appeared; there was no return."""
    user = make_user()
    _open_window(client, db, user, session_for, assets_for,
                 at=CUE_OFFSETS_SECONDS[0] + 1)

    delivery_id = _claim_and_show(client, "active")
    client.post("/api/study/disengagement/start", json={"type": "idle"})
    client.post("/api/study/disengagement/end", json={"ended_by": "return"})

    row = db.query(models.CueDelivery).filter_by(id=delivery_id).first()
    assert row.return_latency_ms is None


# ── PRIMARY MEASURE 2: post-cue retention ─────────────────────────────
def test_retention_measured_to_the_next_disengagement(client, db, make_user,
                                                      session_for, assets_for):
    user = make_user()
    _open_window(client, db, user, session_for, assets_for,
                 at=CUE_OFFSETS_SECONDS[0] + 1)

    delivery_id = _claim_and_show(client, "active")
    row = db.query(models.CueDelivery).filter_by(id=delivery_id).first()
    _shift(db, row, "delivered_at", 90)

    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})

    db.refresh(row)
    assert 85 <= row.post_cue_focus_seconds <= 95
    assert row.return_latency_ms is None


def test_retention_is_the_first_disengagement_only(client, db, make_user,
                                                   session_for, assets_for):
    """Retention is time until they NEXT stop — not until the last time they
    stopped. A later episode must not overwrite it."""
    user = make_user()
    _open_window(client, db, user, session_for, assets_for,
                 at=CUE_OFFSETS_SECONDS[0] + 1)

    delivery_id = _claim_and_show(client, "active")
    row = db.query(models.CueDelivery).filter_by(id=delivery_id).first()
    _shift(db, row, "delivered_at", 30)

    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})
    db.refresh(row)
    first = row.post_cue_focus_seconds

    client.post("/api/study/disengagement/end", json={"ended_by": "return"})
    client.post("/api/study/disengagement/start", json={"type": "idle"})

    db.refresh(row)
    assert row.post_cue_focus_seconds == first


# ── disengagement log ─────────────────────────────────────────────────
def test_episode_records_duration_and_how_it_ended(client, db, make_user,
                                                   session_for, assets_for):
    user = make_user()
    _open_window(client, db, user, session_for, assets_for, at=60)

    client.post("/api/study/disengagement/start", json={"type": "idle"})
    ep = db.query(models.DisengagementEpisode).first()
    _shift(db, ep, "started_at", 12)

    client.post("/api/study/disengagement/end", json={"ended_by": "return"})

    db.refresh(ep)
    assert ep.ended_by == "return"
    assert 11_000 <= ep.duration_ms <= 13_500


def test_double_start_does_not_inflate_the_count(client, db, make_user,
                                                 session_for, assets_for):
    """Idle can fire and then the tab can be switched — one continuous absence
    from the reading, reported twice. Counting two would inflate the
    disengagement count, which is itself an outcome measure."""
    user = make_user()
    _open_window(client, db, user, session_for, assets_for, at=60)

    client.post("/api/study/disengagement/start", json={"type": "idle"})
    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})

    assert db.query(models.DisengagementEpisode).count() == 1


def test_end_reading_closes_an_open_episode(client, db, make_user,
                                            session_for, assets_for):
    """An episode still open at the end would keep a NULL duration and drop
    out of time-on-task — biased in favour of whoever disengaged last."""
    user = make_user()
    _open_window(client, db, user, session_for, assets_for, at=60)

    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})
    client.post("/api/study/session/end-reading")

    ep = db.query(models.DisengagementEpisode).first()
    assert ep.ended_by == "session_end"
    assert ep.duration_ms is not None


def test_episode_links_to_the_cue_that_preceded_it(client, db, make_user,
                                                   session_for, assets_for):
    user = make_user()
    _open_window(client, db, user, session_for, assets_for,
                 at=CUE_OFFSETS_SECONDS[0] + 1)

    _claim_and_show(client, "active")
    client.post("/api/study/disengagement/start", json={"type": "tab_switch"})

    ep = db.query(models.DisengagementEpisode).first()
    assert ep.preceded_by_cue_slot == 1
    assert ep.ms_since_last_cue is not None


def test_disengagement_rejects_unknown_type(client, db, make_user,
                                            session_for, assets_for):
    user = make_user()
    _open_window(client, db, user, session_for, assets_for, at=60)
    r = client.post("/api/study/disengagement/start", json={"type": "bored"})
    assert r.status_code == 422


# ── the frozen protocol ───────────────────────────────────────────────
def test_reactive_routes_accept_but_never_write(client, db, make_user):
    """A participant on an old extension build must degrade quietly, not 404
    mid-session — and must not leave rows in the frozen table."""
    user = make_user()
    client.login(user)

    for route, body in [("/api/research/event", {"event_type": "tab_switch"}),
                        ("/api/research/event/reminder-shown", {}),
                        ("/api/research/event/return", {})]:
        r = client.post(route, json=body)
        assert r.status_code == 200, route
        assert r.json()["ok"] is False

    assert db.query(models.ResearchEvent).count() == 0
