"""Answer storage and the research export.

Two things must survive the trip from a participant tapping a chip to a row
in a CSV: the VALUE, and what kind of measure produced it. The second is the
one that gets lost, because nothing breaks when it does.
"""
from __future__ import annotations

import csv
import io

from app import measure_items as m
from app.database import models

KEY = {"X-Export-Key": "test-export-key"}


def _save(client, timepoint, responses):
    return client.post("/api/measures/responses",
                       json={"timepoint": timepoint, "responses": responses})


# ── provenance ───────────────────────────────────────────────────────────
def test_provenance_is_stamped_from_the_server_not_the_client(
        client, db, make_user):
    u = make_user(code="P1")
    client.login(u)
    _save(client, "pre", {"pi1_pre": 4})

    row = db.query(models.MeasureResponse).filter_by(item_code="pi1_pre").one()
    assert row.measure_status == m.PUBLISHED_ADAPTED
    assert row.battery_version == m.BATTERY_VERSION
    assert row.validated is False
    assert row.phase == 2


def test_hci_items_are_recorded_as_study_specific(client, db, make_user):
    u = make_user(code="P2")
    client.login(u)
    _save(client, "post", {"hci_ease": 5})
    row = db.query(models.MeasureResponse).filter_by(item_code="hci_ease").one()
    assert row.measure_status == m.STUDY_HCI
    assert row.validated is False


def test_an_item_not_in_the_timepoint_is_refused(client, db, make_user):
    """Posting a post-only code to `pre` must not create a row, or the two
    administrations stop being separable."""
    u = make_user(code="P3")
    client.login(u)
    r = _save(client, "pre", {"pi1_post": 5})
    assert "pi1_post" in r.json()["ignored"]
    assert db.query(models.MeasureResponse).count() == 0


# ── the pre/post guarantee ───────────────────────────────────────────────
def test_a_post_answer_never_overwrites_its_pre_counterpart(client, db,
                                                            make_user):
    """The single most important storage property here. Distinct codes AND
    distinct timepoints keep both administrations on the record."""
    u = make_user(code="PP1")
    client.login(u)
    _save(client, "pre", {"pi1_pre": 2, "ie1_pre": 2})
    _save(client, "post", {"pi1_post": 6, "ie1_post": 6})

    vals = {r.item_code: r.value
            for r in db.query(models.MeasureResponse).all()}
    assert vals["pi1_pre"] == 2
    assert vals["pi1_post"] == 6
    assert vals["ie1_pre"] == 2
    assert vals["ie1_post"] == 6


def test_resubmitting_a_page_updates_rather_than_duplicates(client, db,
                                                            make_user):
    u = make_user(code="PP2")
    client.login(u)
    _save(client, "pre", {"pi1_pre": 1})
    _save(client, "pre", {"pi1_pre": 5})
    rows = db.query(models.MeasureResponse).filter_by(item_code="pi1_pre").all()
    assert len(rows) == 1 and rows[0].value == 5


# ── free text ────────────────────────────────────────────────────────────
def test_the_goal_is_stored_as_text_not_a_number(client, db, make_user):
    u = make_user(code="G1")
    client.login(u)
    _save(client, "future_goal", {"future_goal": "تدریس در دانشگاه"})
    row = db.query(models.MeasureResponse).filter_by(
        item_code="future_goal").one()
    assert row.text_value == "تدریس در دانشگاه"
    assert row.value is None


def test_open_feedback_is_stored_as_text(client, db, make_user):
    u = make_user(code="F1")
    client.login(u)
    _save(client, "post", {"feedback_mismatch": "بخش تصویر"})
    row = db.query(models.MeasureResponse).filter_by(
        item_code="feedback_mismatch").one()
    assert row.text_value == "بخش تصویر"


# ── the goal shown above the items ───────────────────────────────────────
def test_pre_and_post_pages_carry_the_participants_own_goal(client, db,
                                                            make_user):
    """The instrumentality wording refers to "this future goal". If the page
    did not carry it, those items would ask about something invisible."""
    u = make_user(code="G2")
    client.login(u)
    _save(client, "future_goal", {"future_goal": "کار در یک شرکت بین‌المللی"})

    for tp in ("pre", "post"):
        body = client.get("/api/measures/items",
                          params={"timepoint": tp}).json()
        assert body["show_goal"] is True
        assert body["future_goal"] == "کار در یک شرکت بین‌المللی"
        assert body["goal_prompt_fa"]


def test_the_goal_page_itself_does_not_echo_the_goal(client, db, make_user):
    u = make_user(code="G3")
    client.login(u)
    body = client.get("/api/measures/items",
                      params={"timepoint": "future_goal"}).json()
    assert body["show_goal"] is False


def test_the_open_prompts_are_advertised_as_optional(client, db, make_user):
    u = make_user(code="G4")
    client.login(u)
    body = client.get("/api/measures/items",
                      params={"timepoint": "post"}).json()
    assert set(body["optional_codes"]) == {"feedback_mismatch",
                                           "feedback_connection_change"}


# ── the chatbot's importance rating ──────────────────────────────────────
def test_chatbot_importance_still_reaches_the_measures_table(client, db,
                                                             make_user):
    """It is asked inside the conversation and is NOT part of the active
    battery. It must still be exported, or a rating the participant gave
    disappears with nothing to show it was collected."""
    from app.routers import eft as eft_router

    u = make_user(code="MIR1")
    eft_router._mirror_goal_importance(db, u, 5)
    db.commit()

    row = db.query(models.MeasureResponse).filter_by(
        item_code="goal_importance").one()
    assert row.value == 5
    assert row.battery_version == m.BATTERY_VERSION
    assert row.measure_status == m.PUBLISHED_ADAPTED


def test_mirroring_twice_does_not_duplicate_the_row(client, db, make_user):
    from app.routers import eft as eft_router

    u = make_user(code="MIR2")
    eft_router._mirror_goal_importance(db, u, 4)
    eft_router._mirror_goal_importance(db, u, 6)
    db.commit()
    rows = db.query(models.MeasureResponse).filter_by(
        item_code="goal_importance").all()
    assert len(rows) == 1 and rows[0].value == 6


# ── CSV export ───────────────────────────────────────────────────────────
def test_measures_csv_carries_id_phase_and_provenance(client, db, make_user):
    u = make_user(code="CSV1")
    client.login(u)
    _save(client, "future_goal", {"future_goal": "هدف من"})
    _save(client, "pre", {"pi1_pre": 3, "goal_feasibility_pre": 5})

    r = client.get("/api/research/export/measures.csv", headers=KEY)
    assert r.status_code == 200
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert rows

    for row in rows:
        assert row["participant_id"] == str(u.id)
        assert row["battery_version"] == m.BATTERY_VERSION
        assert row["measure_status"] and row["phase"] and row["answered_at"]

    by_code = {x["item_code"]: x for x in rows}
    assert by_code["future_goal"]["response_text"] == "هدف من"
    assert by_code["pi1_pre"]["response_value"] == "3"


def test_measures_csv_requires_the_export_key(client):
    assert client.get("/api/research/export/measures.csv").status_code == 403
