"""Routing through the visualization demo.

Stage-machine failures are quiet: a wrong stage sends someone PAST a step
rather than erroring, so they finish having skipped it and nothing complains
until the export is short a measure.
"""
from __future__ import annotations

from app.database import models

FLOW = ["profile", "future_goal", "pre", "eft_chat", "generate",
        "visualize", "post", "done"]


def _stage(client, user):
    client.login(user)
    r = client.get("/api/participant/state")
    assert r.status_code == 200, r.text
    return r.json()["stage"]


def _profile(db, u):
    db.add(models.ParticipantProfile(user_id=u.id, age=22)); db.commit()


def _answer(db, u, timepoint, code=None):
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="t", item_code=code or f"{timepoint}_x",
        timepoint=timepoint, value=1))
    db.commit()


def _goal(db, u, text="گرفتن نمره ۷ در آیلتس"):
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="future_goal", item_code="future_goal",
        timepoint="future_goal", text_value=text))
    db.commit()


def _episode(db, u):
    db.add(models.EFTEpisode(user_id=u.id, episode_json="{}")); db.commit()


def _asset(db, u):
    db.add(models.ReminderAsset(user_id=u.id, asset_index=0,
                                image_url="/static/reminders/x.png",
                                cue="متن", is_generic=False))
    db.commit()


def _seen(db, u):
    db.add(models.UserActivity(user_id=u.id,
                               activity_type="visualization_seen"))
    db.commit()


def test_the_flow_runs_in_order(client, db, make_user):
    u = make_user(code="F1")
    assert _stage(client, u) == "profile"
    _profile(db, u)
    assert _stage(client, u) == "future_goal"
    _goal(db, u)
    assert _stage(client, u) == "pre"
    _answer(db, u, "pre")
    assert _stage(client, u) == "eft_chat"
    _episode(db, u)
    assert _stage(client, u) == "generate"
    _asset(db, u)
    assert _stage(client, u) == "visualize"
    _seen(db, u)
    assert _stage(client, u) == "post"
    _answer(db, u, "post")
    assert _stage(client, u) == "done"


def test_the_goal_is_required_before_the_pre_questionnaire(client, db,
                                                           make_user):
    """Reaching `pre` without a goal would show instrumentality items that
    refer to a goal the participant never wrote."""
    u = make_user(code="F2")
    _profile(db, u)
    assert _stage(client, u) == "future_goal"


def test_the_visualization_is_not_reachable_without_an_image(client, db,
                                                             make_user):
    """Otherwise the screen opens on a blank frame — the first time the
    participant sees their generated future."""
    u = make_user(code="F3")
    _profile(db, u); _goal(db, u); _answer(db, u, "pre"); _episode(db, u)
    assert _stage(client, u) == "generate"


def test_both_arms_take_the_same_path(client, db, make_user):
    """This version has no control condition. `study_group` is still recorded
    but must not route anything — a control participant sent down an arm that
    was built to skip the chatbot would stall there."""
    for arm, code in (("eft", "A1"), ("control", "A2")):
        u = make_user(study_group=arm, code=code)
        _profile(db, u)
        assert _stage(client, u) == "future_goal"
        _goal(db, u)
        assert _stage(client, u) == "pre"
        _answer(db, u, "pre")
        assert _stage(client, u) == "eft_chat"


def test_no_removed_study_stage_is_ever_emitted(client, db, make_user):
    """The reading task, extension setup and scheduled cues still exist in
    the codebase and are still tested. They must not appear in this flow."""
    u = make_user(code="F4")
    seen = set()
    _profile(db, u); seen.add(_stage(client, u))
    _goal(db, u); seen.add(_stage(client, u))
    _answer(db, u, "pre"); seen.add(_stage(client, u))
    _episode(db, u); seen.add(_stage(client, u))
    _asset(db, u); seen.add(_stage(client, u))
    _seen(db, u); seen.add(_stage(client, u))
    _answer(db, u, "post"); seen.add(_stage(client, u))

    for removed in ("session", "session1", "session2", "inventory",
                    "control_goal", "control_goal_context",
                    "manipulation_check", "feedback", "post_task"):
        assert removed not in seen, f"{removed} appeared in the flow"
    assert seen <= set(FLOW)


def test_marking_the_visualization_seen_is_idempotent(client, db, make_user):
    """A reload or double tap must not add a second activity row, or the log
    stops being a record of what happened."""
    u = make_user(code="F5")
    client.login(u)
    assert client.post("/api/participant/visualization-seen").status_code == 201
    assert client.post("/api/participant/visualization-seen").status_code == 201
    rows = (db.query(models.UserActivity)
            .filter_by(user_id=u.id,
                       activity_type="visualization_seen").all())
    assert len(rows) == 1
