"""The study's measurement battery: what is asked, where, and to whom.

Kept in one file so the item text, the response options, the timepoint and the
arm are visible together — the questionnaire is study design, not UI detail,
and it has to be readable by someone checking the protocol rather than the
code.

TWO KINDS OF ITEM LIVE HERE, and the difference matters for the write-up:

  PUBLISHED INSTRUMENTS — used verbatim, only translated. Do not reword these
  to make them clearer; a reworded validated item is a different instrument
  and its published properties no longer apply.
      · fsc      Ersner-Hershfield et al. (2009) overlapping-circles measure,
                 adapted from Aron, Aron & Smollan (1992). The TIME HORIZON is
                 a study parameter, not part of the instrument — published
                 studies use 3 months, 10 years, and age 70. One year is used
                 here because it matches the horizon participants choose in
                 the imagining task, and because a decade-scale forecast is a
                 harsh thing to ask this population.
      · asayama  EFT manipulation check, 6-point.
    Neither has a validated Persian version. The wording below is a
    forward/back translation and must be reported as such.

  STUDY-AUTHORED ITEMS — written for this study, not validated, and never to
  be described as scales. Reword these freely.
      · intention, reminder, attention_check

TIMEPOINTS
    baseline    before anything, both arms
    post_chat   immediately after the EFT episode is confirmed, eft arm only
    session1/2  immediately after each reading session, both arms
    closing     end of study, both arms
  fsc and intention appear at BOTH baseline and closing on purpose: the
  analysis needs a change score, and a single end-of-study measurement cannot
  show that anything moved.
"""
from __future__ import annotations

# ── response option sets ────────────────────────────────────────────────
# 1..7 pairs of increasingly overlapping circles. Rendered as a picture, not
# as words — which is also why this measure suits participants who find long
# Persian questionnaires heavy going.
CIRCLES = {"kind": "circles", "min": 1, "max": 7}

LIKERT5 = {
    "kind": "likert", "min": 1, "max": 5,
    "labels_fa": {1: "خیلی کم", 2: "کم", 3: "تا حدی", 4: "زیاد", 5: "خیلی زیاد"},
}

# Asayama uses a 6-point agreement scale; kept at 6 rather than folded into
# the 5-point set above, because collapsing a published response format is
# exactly the kind of silent change that invalidates an instrument.
LIKERT6 = {
    "kind": "likert", "min": 1, "max": 6,
    "labels_fa": {1: "کاملاً مخالفم", 2: "مخالفم", 3: "تا حدی مخالفم",
                  4: "تا حدی موافقم", 5: "موافقم", 6: "کاملاً موافقم"},
}

HOURS = {
    "kind": "choice",
    "options_fa": ["۰ ساعت", "کمتر از ۱ ساعت", "۱ تا ۳ ساعت",
                   "۳ تا ۵ ساعت", "بیشتر از ۵ ساعت"],
}

TIMES = {
    "kind": "choice",
    "options_fa": ["هیچ", "۱ بار", "۲ تا ۳ بار", "۴ تا ۵ بار", "بیشتر"],
}


FSC_SOURCE = (
    "Ersner-Hershfield, H., Garton, M. T., Ballard, K., Samanez-Larkin, "
    "G. R., & Knutson, B. (2009). Don't stop thinking about tomorrow: "
    "Individual differences in future self-continuity account for saving. "
    "Judgment and Decision Making, 4(4), 280-286. Circle format adapted "
    "from Aron, Aron & Smollan (1992), Inclusion of Other in the Self."
)

ASAYAMA_SOURCE = (
    "Asayama et al. — EFT manipulation check, 5 statements, 6-point scale. "
    "SUPPLIED BY THE RESEARCHER; full citation still to be filled in before "
    "submission."
)

STUDY_AUTHORED = "Written for this study. NOT a validated instrument."


def _item(code, instrument, text_fa, scale, reverse=False,
          source_en=None, source=None):
    """One item.

    source_en / source are the provenance and are NOT optional decoration:
    a reader has to be able to tell, per item, whether the Persian is a
    translation of published wording or something written for this study.
    Items with source_en=None are study-authored and must never be described
    as validated scales.
    """
    return {"code": code, "instrument": instrument, "text_fa": text_fa,
            "scale": scale, "reverse": reverse,
            "source_en": source_en, "source": source}


# ── Future self-continuity (published, verbatim, translated) ────────────
# Horizon fixed at one year — see the module docstring.
FSC = [
    _item("fsc_similarity", "fsc",
          "جفت دایره‌ای رو انتخاب کن که به نظرت میزانِ «شباهت» بین خودِ الانِ "
          "تو و خودت یک سال دیگه رو بهتر نشون می‌ده.",
          CIRCLES,
          source_en=("Choose the pair of circles that you feel best "
                     "represents the level of SIMILARITY between your "
                     "present self and yourself [horizon] in the future."),
          source=FSC_SOURCE),
    _item("fsc_connected", "fsc",
          "جفت دایره‌ای رو انتخاب کن که به نظرت میزانِ «ارتباط» بین خودِ الانِ "
          "تو و خودت یک سال دیگه رو بهتر نشون می‌ده.",
          CIRCLES,
          source_en=("Choose the pair of circles that you feel best "
                     "represents the level of CONNECTION between your "
                     "present self and yourself [horizon] in the future."),
          source=FSC_SOURCE),
]

# ── Study intention (study-authored) ────────────────────────────────────
# Three items rather than one so an internal-consistency estimate can be
# reported; a lone number has no reliability to speak of.
INTENTION = [
    _item("intent_hours", "intention",
          "هفته‌ی آینده قصد داری چند ساعت انگلیسی کار کنی؟", HOURS,
          source=STUDY_AUTHORED),
    _item("intent_sessions", "intention",
          "هفته‌ی آینده قصد داری چند بار برای انگلیسی بشینی؟", TIMES,
          source=STUDY_AUTHORED),
    _item("intent_confidence", "intention",
          "چقدر مطمئنی که این برنامه رو عملی می‌کنی؟", LIKERT5,
          source=STUDY_AUTHORED),
]

# ── EFT manipulation check (published, verbatim, translated) ────────────
# A GATE, not an outcome: it verifies the imagining task worked. Deliberately
# asks only about the act of imagining — never about whether the future is
# likely — which is what keeps it safe for participants who find the future
# genuinely uncertain.
ASAYAMA = [
    _item("asayama_1", "asayama",
          "صحنه‌ای واضح از آینده را در ذهنم تصور کردم.", LIKERT6,
          source_en='I imagined a vivid scene of the future in my mind.',
          source=ASAYAMA_SOURCE),
    _item("asayama_2", "asayama",
          "صحنه‌های مشخصی از آینده را در ذهنم تصور کردم.", LIKERT6,
          source_en='I imagined specific scenes of the future in my mind.',
          source=ASAYAMA_SOURCE),
    _item("asayama_3", "asayama",
          "رویدادهای آینده را با جزئیات در ذهنم تصور کردم.", LIKERT6,
          source_en='I imagined future events in detail in my mind.',
          source=ASAYAMA_SOURCE),
    _item("asayama_4", "asayama",
          "تصویر روشنی از صحنه‌های مشخص آینده در ذهنم ساختم.", LIKERT6,
          source_en='I imagined clear scenes of specific future scenes in my mind.',
          source=ASAYAMA_SOURCE),
    _item("asayama_5", "asayama",
          "صحنه‌های مشخص آینده را طوری تصور کردم که انگار واقعاً داشتم "
          "تجربه‌شان می‌کردم.", LIKERT6,
          source_en='I imagined specific future scenes in my mind as if I were actually experiencing them.',
          source=ASAYAMA_SOURCE),
]

# ── Post-session (study-authored) ───────────────────────────────────────
# The only block BOTH arms answer about the manipulation itself, so it is the
# only self-report that can be compared between them. The third item is the
# proximal mechanism step — whether the reminder actually put the goal back in
# mind — and without it the path from reminder to attention has a gap.
REMINDER = [
    _item("reminder_helped", "reminder",
          "چقدر یادآورها کمکت کردن به مطالعه برگردی؟", LIKERT5,
          source=STUDY_AUTHORED),
    _item("reminder_distracted", "reminder",
          "چقدر یادآورها حواست رو پرت کردن؟", LIKERT5, reverse=True,
          source=STUDY_AUTHORED),
    _item("goal_thought", "reminder",
          "در طول این جلسه چقدر به هدف انگلیسی‌ات فکر کردی؟", LIKERT5,
          source=STUDY_AUTHORED),
]

# ── Data quality (study-authored) ───────────────────────────────────────
ATTENTION_CHECK = [
    _item("attn_1", "attention_check",
          "برای اینکه مطمئن بشیم با دقت جواب می‌دی، لطفاً برای این سوال "
          "گزینه‌ی «تا حدی» رو انتخاب کن.", LIKERT5,
          source=STUDY_AUTHORED),
]

# ── what is asked when, and of whom ─────────────────────────────────────
# arm: None = both arms.
TIMEPOINTS: dict[str, dict] = {
    "baseline": {"arm": None, "items": FSC + INTENTION},
    "post_chat": {"arm": "eft", "items": ASAYAMA},
    "session1": {"arm": None, "items": REMINDER},
    "session2": {"arm": None, "items": REMINDER},
    "closing": {"arm": None, "items": FSC + INTENTION + ATTENTION_CHECK},
}

SOURCE_NOTE = (
    "fsc: overlapping-circles future self-continuity measure "
    "(Ersner-Hershfield et al., 2009; adapted from Aron et al., 1992), "
    "horizon set to one year, forward/back translated into Persian — no "
    "validated Persian version exists. "
    "asayama: EFT manipulation check, 6-point, forward/back translated. "
    "intention, reminder, attention_check: study-authored, not validated."
)


def items_for(timepoint: str, study_group: str | None) -> list[dict]:
    """Items due at this timepoint for this arm, or [] if none apply."""
    spec = TIMEPOINTS.get(timepoint)
    if spec is None:
        return []
    if spec["arm"] is not None and (study_group or "eft") != spec["arm"]:
        return []
    return spec["items"]
