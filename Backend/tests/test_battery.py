"""The active measurement battery for the visualization demo.

These failures are silent by nature: a page that serves the wrong items still
renders, a post answer that overwrites its pre counterpart still saves, and an
item whose `kind` the client cannot draw still appears as *something*. Nothing
errors — the study just stops measuring what it claims to.
"""
from __future__ import annotations

from app import measure_items as m

# Every scale kind the Flutter measures page can draw. Adding a kind here
# without adding a branch there is the bug this guards: the page falls through
# to a rating scale, so an open-ended prompt silently collects a number.
RENDERABLE_KINDS = {"likert", "choice", "text", "duration"}


def test_battery_version_is_stamped_on_every_item():
    for item in m.ALL_ITEMS:
        assert item["battery_version"] == m.BATTERY_VERSION, item["code"]


def test_every_item_uses_a_renderable_kind():
    for item in m.ALL_ITEMS:
        assert item["response_type"] in RENDERABLE_KINDS, item["code"]


def test_every_item_exposes_helper_text_even_when_empty():
    """The client reads this key unconditionally."""
    for item in m.ALL_ITEMS:
        assert isinstance(item.get("helper_fa"), str), item["code"]


def test_nothing_claims_a_validated_persian_scale():
    for item in m.ALL_ITEMS:
        assert item["validated_status"] is False, item["code"]
        assert item["measure_status"] != m.PUBLISHED_ORIGINAL, item["code"]


def test_item_codes_are_unique():
    codes = [i["code"] for i in m.ALL_ITEMS]
    assert len(codes) == len(set(codes))


# ── the flow's three timepoints ──────────────────────────────────────────
def test_only_the_three_expected_timepoints_exist():
    assert set(m.TIMEPOINTS) == {"future_goal", "pre", "post"}


def test_goal_is_collected_before_the_pre_questionnaire():
    """The instrumentality items ask about "this future goal". Collected
    after them, they would have no referent."""
    assert m.TIMEPOINTS["future_goal"]["phase"] < m.TIMEPOINTS["pre"]["phase"]
    assert [i["code"] for i in m.items_for("future_goal")] == ["future_goal"]


def test_the_goal_question_is_free_text():
    item = m.item_by_code("future_goal")
    assert item["response_type"] == "text"
    assert item["scale"].get("multiline") is True


# ── pre / post pairing, which is the whole design ────────────────────────
def test_pi_and_ie_are_asked_at_both_pre_and_post():
    pre = {i["code"] for i in m.items_for("pre")}
    post = {i["code"] for i in m.items_for("post")}
    for n in range(1, 6):
        assert f"pi{n}_pre" in pre and f"pi{n}_post" in post
    for n in range(1, 7):
        assert f"ie{n}_pre" in pre and f"ie{n}_post" in post


def test_pre_and_post_wording_is_word_for_word_identical():
    """A pre/post comparison where the wording drifted measures the wording,
    not the intervention."""
    by_code = {i["code"]: i for i in m.ALL_ITEMS}
    for stem in [f"pi{n}" for n in range(1, 6)] + [f"ie{n}" for n in range(1, 7)]:
        a, b = by_code[f"{stem}_pre"], by_code[f"{stem}_post"]
        assert a["text_fa"] == b["text_fa"], stem
        assert a["scale_min"] == b["scale_min"], stem
        assert a["scale_max"] == b["scale_max"], stem
        assert a["scale_labels"] == b["scale_labels"], stem


def test_pre_and_post_use_distinct_item_codes():
    """Distinct codes AND distinct timepoints are what stop a post answer
    overwriting its pre counterpart — the storage key is
    (user, item_code, timepoint)."""
    pre = {i["code"] for i in m.items_for("pre")}
    post = {i["code"] for i in m.items_for("post")}
    assert not (pre & post)


def test_feasibility_is_pre_only():
    assert "goal_feasibility_pre" in {i["code"] for i in m.items_for("pre")}
    assert not [i for i in m.items_for("post")
                if i["code"].startswith("goal_feasibility")]


def test_pi_uses_five_points_and_ie_uses_six():
    """Two different published response formats. Collapsing either into the
    other would silently change the instrument."""
    for n in range(1, 6):
        item = m.item_by_code(f"pi{n}_pre")
        assert (item["scale_min"], item["scale_max"]) == (1, 5), item["code"]
    for n in range(1, 7):
        item = m.item_by_code(f"ie{n}_pre")
        assert (item["scale_min"], item["scale_max"]) == (1, 6), item["code"]


def test_scales_with_the_same_width_keep_their_own_anchors():
    """Feasibility, applicability and agreement are all 1-6; only the anchors
    tell them apart, so they must not share one scale object."""
    assert m.item_by_code("goal_feasibility_pre")["scale_labels"][1] \
        == "اصلاً امکان‌پذیر نیست"
    assert m.item_by_code("eft_vividness")["scale_labels"][1] \
        == "اصلاً صدق نمی‌کند"
    assert m.item_by_code("ie1_pre")["scale_labels"][1] == "کاملاً مخالفم"


# ── post-only blocks ─────────────────────────────────────────────────────
def test_post_carries_the_five_eft_process_items():
    codes = [i["code"] for i in m.items_for("post")]
    for c in ("eft_vividness", "eft_concreteness", "eft_detail",
              "eft_clarity", "eft_simulated_experience"):
        assert c in codes


def test_post_carries_all_eight_hci_items():
    hci = [i for i in m.items_for("post") if i["code"].startswith("hci_")]
    assert len(hci) == 8


def test_the_negative_hci_items_are_marked_reverse():
    """A high score on these is a WORSE outcome. Unmarked, they would be
    averaged in the wrong direction."""
    for code in ("hci_emotional_burden", "hci_pressure_to_believe",
                 "hci_unrealistic"):
        assert m.item_by_code(code)["reverse"] is True, code


def test_open_feedback_is_free_text_and_optional():
    codes = {i["code"] for i in m.items_for("post")}
    assert {"feedback_mismatch", "feedback_connection_change"} <= codes
    for code in ("feedback_mismatch", "feedback_connection_change"):
        assert m.item_by_code(code)["response_type"] == "text"
        assert code in m.OPTIONAL_CODES


def test_only_the_open_prompts_are_optional():
    """Everything else must be answered before the page will submit."""
    assert m.OPTIONAL_CODES == {"feedback_mismatch",
                                "feedback_connection_change"}


# ── the goal is shown where it is referred to ────────────────────────────
def test_the_goal_is_displayed_above_both_pre_and_post():
    assert m.shows_goal("pre")
    assert m.shows_goal("post")
    # Not on the page where it is being written for the first time.
    assert not m.shows_goal("future_goal")


# ── the removed protocol cannot come back ───────────────────────────────
def test_no_reading_task_or_reminder_item_is_active():
    banned = ("task_goal_connection", "reminder_", "cue_", "control_",
              "tipi_", "sus_", "fsc_", "intended_study_time",
              "eft_imagery_")
    for item in m.ALL_ITEMS:
        for b in banned:
            assert not item["code"].startswith(b), (
                f"{item['code']} belongs to a superseded protocol")


def test_superseded_items_are_recorded_but_never_served():
    active = {i["code"] for i in m.ALL_ITEMS}
    assert m.DEPRECATED_ITEMS
    for code in m.DEPRECATED_ITEMS:
        assert code not in active, f"{code} is deprecated but still served"


def test_items_for_ignores_study_group():
    """One path for everyone in this version. The parameter is kept so older
    callers keep working, but it must not change what is served."""
    for tp in m.TIMEPOINTS:
        assert m.items_for(tp, "eft") == m.items_for(tp, "control")
