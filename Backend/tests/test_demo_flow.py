"""The complete participant flow, walked end to end.

The failure this catches is the one that actually happened in an earlier
version: a screen asks for a timepoint the server no longer serves, gets a
422, and the participant loops forever with nothing in the UI to explain it.
"""
from __future__ import annotations

import json

from app import measure_items as m
from app.database import models


def _answer_value(item):
    if item["response_type"] == "text":
        return "پاسخ نمونه"
    if item["response_type"] == "duration":
        return {"hours": 1, "minutes": 0}
    return item["scale_min"]


def test_a_new_participant_walks_the_whole_flow_without_looping(
        client, db, make_user):
    u = make_user(code="W1")
    client.login(u)
    seen = []

    for _ in range(12):
        stage = client.get("/api/participant/state").json()["stage"]
        seen.append(stage)
        if stage == "done":
            break
        if stage == "reading":
            assert client.post("/api/events/session/start").status_code == 201
            assert client.post("/api/events/end_session").status_code == 200
        elif stage == "profile":
            db.add(models.ParticipantProfile(user_id=u.id, age=23)); db.commit()
        elif stage == "eft_chat":
            db.add(models.EFTEpisode(user_id=u.id, episode_json="{}")); db.commit()
        elif stage == "generate":
            db.add(models.ReminderAsset(
                user_id=u.id, asset_index=0, is_generic=False,
                image_url="/static/reminders/x.png", cue="متن آینده"))
            db.commit()
        elif stage == "visualize":
            assert client.post(
                "/api/participant/visualization-seen").status_code == 201
        else:
            # A questionnaire stage MUST resolve to a real timepoint with
            # items, or the client has nothing to submit and loops.
            r = client.get("/api/measures/items",
                           params={"timepoint": stage})
            assert r.status_code == 200, f"{stage} -> {r.status_code} {r.text}"
            items = r.json()["items"]
            assert items, f"stage {stage!r} served no items"
            client.post("/api/measures/responses", json={
                "timepoint": stage,
                "responses": {i["code"]: _answer_value(i) for i in items},
            })

    assert seen == ["eft_chat", "generate", "visualize", "reading", "done"], seen
    assert db.query(models.MeasureResponse).filter_by(user_id=u.id).count() == 0
    assert seen[-1] == "done", seen
    assert len(seen) == len(set(seen)), f"stage repeated: {seen}"


def test_every_questionnaire_stage_names_a_real_timepoint():
    """The loop's root cause last time: a client asked for a timepoint the
    battery had removed and got 422 with no way forward."""
    assert {"future_goal", "pre", "post"} <= set(m.TIMEPOINTS)


def test_a_removed_timepoint_is_refused_rather_than_silently_empty(
        client, db, make_user):
    u = make_user(code="W2")
    client.login(u)
    for gone in ("baseline", "post_task", "control_goal", "closing"):
        r = client.get("/api/measures/items", params={"timepoint": gone})
        assert r.status_code == 422, gone


# ── the goal reaches the chatbot ─────────────────────────────────────────
def test_the_chatbot_starts_from_the_goal_already_collected(
        client, db, make_user):
    """The participant writes their goal on its own screen. Asking for it
    again as the chatbot's first question would produce two goals per person
    with nothing saying which the generated future is about."""
    from app.routers import eft as eft_router

    u = make_user(code="S1")
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="future_goal", item_code="future_goal",
        timepoint="future_goal", text_value="تدریس در دانشگاه"))
    db.commit()

    eft_router._seed_goal_from_future_goal(db, u)
    db.commit()

    state = db.query(models.EFTChatState).filter_by(user_id=u.id).one()
    fields = json.loads(state.fields_json)
    assert fields["goal"] == "تدریس در دانشگاه"
    # Step 0 is the goal question; starting at 1 is what skips it.
    assert state.current_step == 1


def test_seeding_never_overwrites_a_conversation_in_progress(
        client, db, make_user):
    from app.routers import eft as eft_router

    u = make_user(code="S2")
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="future_goal", item_code="future_goal",
        timepoint="future_goal", text_value="هدف تازه"))
    db.add(models.EFTChatState(
        user_id=u.id, current_step=3,
        fields_json=json.dumps({"goal": "هدف قدیمی", "when": "یک سال دیگه"},
                               ensure_ascii=False)))
    db.commit()

    eft_router._seed_goal_from_future_goal(db, u)
    db.commit()

    state = db.query(models.EFTChatState).filter_by(user_id=u.id).one()
    fields = json.loads(state.fields_json)
    assert fields["goal"] == "هدف قدیمی"
    assert state.current_step == 3


def test_without_a_goal_the_chatbot_asks_its_own_question(client, db,
                                                          make_user):
    """Better than opening a conversation about nothing."""
    from app.routers import eft as eft_router

    u = make_user(code="S3")
    eft_router._seed_goal_from_future_goal(db, u)
    db.commit()
    assert db.query(models.EFTChatState).filter_by(user_id=u.id).first() is None


def test_a_blank_goal_is_treated_as_no_goal(client, db, make_user):
    from app.routers import eft as eft_router

    u = make_user(code="S4")
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="future_goal", item_code="future_goal",
        timepoint="future_goal", text_value="   "))
    db.commit()
    eft_router._seed_goal_from_future_goal(db, u)
    db.commit()
    assert db.query(models.EFTChatState).filter_by(user_id=u.id).first() is None


def test_the_seeded_chatbot_resumes_at_importance_then_when(client, db,
                                                            make_user):
    """The behavioural half of the seeding contract.

    A seeded state must look, to the chat service, exactly like a participant
    who just answered the goal question: the importance chip row fires next,
    and after it the conversation continues at `when` — never back to `goal`.
    No turn logic was changed to achieve this, so this test is what proves the
    seed lands in a state the existing machine already understands.
    """
    from app.routers import eft as eft_router
    from app.services.eft_chat_service_v2 import EFTChatServiceV2, QUESTIONS

    u = make_user(code="S5")
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="future_goal", item_code="future_goal",
        timepoint="future_goal", text_value="کار در یک شرکت بین‌المللی"))
    db.commit()
    eft_router._seed_goal_from_future_goal(db, u)
    db.commit()

    service = EFTChatServiceV2(db, u.id)

    # Opening turn: the rating, not a question about the goal.
    first = service.process_message(None)
    assert first["awaiting_importance"] is True
    assert first["collected"][0] is True, "the goal must already be collected"

    # Rating given → the conversation moves to `when`, step 1.
    after = service.process_message(None, importance=5)
    assert after["awaiting_importance"] is False
    assert after["question_index"] == 1
    assert QUESTIONS[1]["key"] == "when"



def test_the_visualization_shows_the_participants_own_future_in_both_arms(
        client, db, make_user):
    """Signup still assigns study_group, and /api/extension/reminder-set
    withholds personalized assets from the control arm — correct for the
    two-arm reminder study, wrong here where everyone builds a future.

    Without a separate read, roughly half of all participants would reach the
    visualization screen and be shown the SHARED GENERIC image instead of
    their own. Nothing errors; the wrong picture just appears.
    """
    for arm, code in (("eft", "V1"), ("control", "V2")):
        u = make_user(study_group=arm, code=code)
        db.add(models.ReminderAsset(
            user_id=u.id, asset_index=0, is_generic=False,
            image_url=f"/static/reminders/{code}.png",
            cue="صحنه‌ی شخصی من"))
        db.commit()

        client.login(u)
        body = client.get("/api/eft/generated-future").json()
        assert body["ready"] is True, arm
        assert body["image_url"] == f"/static/reminders/{code}.png", arm
        assert body["cue"] == "صحنه‌ی شخصی من", arm


def test_the_visualization_read_says_so_when_nothing_was_generated(
        client, db, make_user):
    """The screen has to distinguish "not ready" from "broken" so it can show
    a plain message instead of a blank frame."""
    u = make_user(code="V3")
    client.login(u)
    body = client.get("/api/eft/generated-future").json()
    assert body["ready"] is False
    assert body["image_url"] is None and body["cue"] is None


def test_the_generic_set_is_never_returned_as_a_personal_future(
        client, db, make_user):
    """A generic asset in the table must not be mistaken for the
    participant's own scene."""
    u = make_user(code="V4")
    db.add(models.ReminderAsset(
        user_id=u.id, asset_index=0, is_generic=True,
        image_url="/static/generic/generic_reminder_0.png",
        cue="مطالعه را ادامه بده."))
    db.commit()
    client.login(u)
    assert client.get("/api/eft/generated-future").json()["ready"] is False


def test_new_signup_goes_to_chat_without_a_profile_questionnaire(client, db):
    response = client.post('/api/auth/signup', json={
        'participant_id': 'product-signup-check', 'password': 'test-password-123',
    })
    assert response.status_code == 201, response.text
    body = response.json()
    user = db.get(models.User, body['user']['id'])
    assert db.query(models.ParticipantProfile).filter_by(user_id=user.id).count() == 0
    client.login(user)
    assert client.get('/api/participant/state').json()['stage'] == 'eft_chat'


def test_optional_waiting_feedback_is_saved_without_starting_reading(client, db, make_user):
    user = make_user(code='PRODUCT-FEEDBACK')
    client.login(user)
    response = client.post('/api/events/log', json={
        'event_type': 'product_feedback',
        'details': {'chat_experience': 4, 'scale_min': 1, 'scale_max': 5},
    })
    assert response.status_code in (200, 201), response.text
    saved = db.query(models.UserActivity).filter_by(
        user_id=user.id, activity_type='product_feedback').one()
    assert saved.extra_data['chat_experience'] == 4
    assert saved.extra_data['scale_max'] == 5
    assert db.query(models.Session).filter_by(user_id=user.id).count() == 0
