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


def test_product_chat_skips_importance_rating(client, db, make_user):
    from app.routers import eft as eft_router
    from app.services.eft_chat_service_v2 import EFTChatServiceV2, QUESTIONS

    u = make_user(code="S5")
    db.add(models.MeasureResponse(
        user_id=u.id, instrument="future_goal", item_code="future_goal",
        timepoint="future_goal", text_value="کار در یک شرکت بین‌المللی"))
    db.commit()
    eft_router._seed_goal_from_future_goal(db, u)
    db.commit()
    first = EFTChatServiceV2(db, u.id).process_message(None)
    assert first["awaiting_importance"] is False
    assert first["collected"][0] is True
    assert first["question_index"] == 1
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


def test_place_reply_cannot_drift_into_objects_or_invent_a_scene(db, make_user, monkeypatch):
    from app.services.eft_chat_service_v2 import EFTChatServiceV2, QUESTIONS
    user = make_user(code='STEP-PLACE')
    db.add(models.EFTChatState(user_id=user.id, current_step=2,
        fields_json=json.dumps({'goal': 'فارغ‌التحصیلی', 'when': 'صبح آخر ترم'})))
    db.commit()
    service = EFTChatServiceV2(db, user.id)
    monkeypatch.setattr(service, '_llm_turn', lambda *args, **kwargs: {
        'question_status': 'needs_more',
        'reply': 'هوا خنک است. چه وسایلی همراهت است؟',
        'extracted_answer': None,
    })
    first = service.process_message('دانشکده کامپیوتر، طبقه هشت')
    assert first['question_index'] == 2
    assert 'دقیقاً کجایی' in first['bot']
    assert 'خنک' not in first['bot'] and 'وسایلی' not in first['bot']

    monkeypatch.setattr(service, '_llm_turn', lambda *args, **kwargs: {
        'question_status': 'collected',
        'reply': 'هوا خنک است و صدای قدم‌ها می‌آید.',
        'extracted_answer': 'دانشکده کامپیوتر، طبقه هشت',
        'next_question': 'چه چیزهایی اطرافت می‌بینی؟',
    })
    second = service.process_message('همون طبقه هشت')
    assert second['question_index'] == 3
    assert second['bot'] == QUESTIONS[3]['text']
    state = db.query(models.EFTChatState).filter_by(user_id=user.id).one()
    fields = json.loads(state.fields_json)
    assert fields['where'] == 'دانشکده کامپیوتر، طبقه هشت'
    assert not fields.get('objects')


def test_english_chat_covers_all_steps_and_saves_language(client, db, make_user, monkeypatch):
    from app.services.eft_chat_service_v2 import EFTChatServiceV2
    from app.services.chat_languages import QUESTIONS_EN
    user = make_user(code='LANG-EN')
    client.login(user)
    monkeypatch.setattr(EFTChatServiceV2, '_llm_turn', lambda self, fields, qi, history, **kw: {
        'question_status': 'collected', 'extracted_answer': history[-1]['content'],
        'reply': 'Invented scene that must not be shown.', 'next_question': 'Wrong step?',
    })
    first = client.post('/api/eft/chat', json={'message': '', 'language': 'en'}).json()
    assert 'long-term goal' in first['bot']
    answers = ['Write a book', 'Next spring, morning', 'My home office',
               'Sharing my manuscript', 'A book and desk', 'My friend', 'Proud and calm']
    for index, answer in enumerate(answers):
        result = client.post('/api/eft/chat', json={'message': answer, 'language': 'en'}).json()
        if index < 6:
            assert result['question_index'] == index + 1
            assert result['bot'] == QUESTIONS_EN[index + 1]
    assert 'confirm' in result['bot']
    assert 'Goal: Write a book' in result['bot']
    final = client.post('/api/eft/chat', json={'message': 'confirm', 'language': 'en'}).json()
    assert final['can_start_session'] is True
    episode = db.query(models.EFTEpisode).filter_by(user_id=user.id).one()
    assert json.loads(episode.episode_json)['language'] == 'en'


def test_switching_chat_language_preserves_answers_and_step(client, db, make_user, monkeypatch):
    from app.services.eft_chat_service_v2 import EFTChatServiceV2
    from app.services.chat_languages import QUESTIONS_EN
    user = make_user(code='LANG-SWITCH')
    client.login(user)
    db.add(models.EFTChatState(user_id=user.id, current_step=2,
        fields_json=json.dumps({'goal': 'My project', 'when': 'Next spring', '_language': 'fa'})))
    db.commit()
    english = client.post('/api/eft/chat', json={'message': '', 'language': 'en'}).json()
    assert english['question_index'] == 2
    assert english['bot'] == QUESTIONS_EN[2]
    ideas = client.post('/api/eft/inspire?language=en').json()['suggestions']
    assert ideas and all(not any('\u0600' <= ch <= '\u06ff' for ch in idea) for idea in ideas)
    persian = client.post('/api/eft/chat', json={'message': '', 'language': 'fa'}).json()
    assert persian['question_index'] == 2
    assert 'کجایی' in persian['bot']
    state = db.query(models.EFTChatState).filter_by(user_id=user.id).one()
    assert json.loads(state.fields_json)['goal'] == 'My project'


def test_manual_scene_keeps_selected_language_for_image_caption(client, db, make_user):
    user = make_user(code='MANUAL-EN')
    client.login(user)
    answers = dict(zip(['goal', 'when', 'where', 'action', 'objects', 'who', 'feeling'],
        ['My book', 'Next spring', 'At home', 'Writing', 'A desk', 'A friend', 'Proud']))
    response = client.post('/api/eft/manual', json={'answers': answers, 'language': 'en'})
    assert response.status_code == 200, response.text
    episode = db.query(models.EFTEpisode).filter_by(user_id=user.id).one()
    assert json.loads(episode.episode_json)['language'] == 'en'
