"""The study's active measurement battery.

Kept in one file so item text, response options, phase and timepoint are
visible together — the questionnaire is study design, not UI detail, and has
to be readable by someone checking the protocol rather than the code.

════════════════════════════════════════════════════════════════════════
ACTIVE FLOW — battery_version research_methods_v1
════════════════════════════════════════════════════════════════════════
THE AUDIENCE: students in a research-methods course. Every item below
therefore asks about the participant's own RESEARCH WORK and the academic
goal it serves (defence, graduation, publication) — not about language
learning, which is what the previous version of this battery asked about.

  1  future_goal   the participant's own future goal, in their words
  2  pre           feasibility (PRE only) · Perceived Instrumentality ×5
                   · Intended Effort ×6
  3  (EFT chatbot, personalized text, personalized image — unchanged)
  4  (visualization screen)
  5  post          the SAME PI ×5 and IE ×6, then EFT process ×5,
                   HCI evaluation ×8, and two open-ended prompts

THE GOAL IS COLLECTED ONCE AND REUSED EVERYWHERE. It is shown above the PI
items at pre, seeded into the chatbot as its `goal` so the participant is
never asked to invent a second one, and shown again above the PI items at
post. Pre and post are separate timepoints, so a post answer can never
overwrite its pre counterpart.

THE BATTERY VERSION CHANGED WITH THE WORDING. The PI and IE items were
reworded from "learning English" to "my research", so an answer collected
under the old wording is a different measurement. Every row carries the
version it was collected under, and the export sorts by it, so the two
cannot be pooled by accident.

════════════════════════════════════════════════════════════════════════
PROVENANCE
════════════════════════════════════════════════════════════════════════
`measure_status` records what each item IS, because the difference decides
how it may be described:

  published_adapted      published item whose wording was CHANGED for this
                         context — no longer verbatim, so its published
                         psychometrics no longer transfer
  study_specific_hci     researcher-written item evaluating the artifact
  study_specific_open_ended   researcher-written qualitative prompt

`validated_status` is False throughout. Nothing here has a validated Persian
version, and a published English item translated for this study is a
translated adaptation, never a validated Persian scale.
"""
from __future__ import annotations

BATTERY_VERSION = "research_methods_v1"

PUBLISHED_ORIGINAL = "published_original"
PUBLISHED_TRANSLATED = "published_translated"
PUBLISHED_ADAPTED = "published_adapted"
STUDY_HCI = "study_specific_hci"
STUDY_OPEN = "study_specific_open_ended"
DEPRECATED = "deprecated"


# ── response option sets ────────────────────────────────────────────────
# Anchors are part of an instrument's response format, so each set is
# defined once and reused rather than retyped per item.

# Perceived Instrumentality: 1-5 agreement, every point labelled.
LIKERT5_AGREE = {
    "kind": "likert", "min": 1, "max": 5,
    "labels_fa": {1: "کاملاً مخالفم", 2: "مخالفم", 3: "نه موافقم نه مخالفم",
                  4: "موافقم", 5: "کاملاً موافقم"},
}

# Intended Effort and the HCI block: 1-6 agreement, every point labelled.
LIKERT6_AGREE = {
    "kind": "likert", "min": 1, "max": 6,
    "labels_fa": {1: "کاملاً مخالفم", 2: "مخالفم", 3: "تا حدی مخالفم",
                  4: "تا حدی موافقم", 5: "موافقم", 6: "کاملاً موافقم"},
}

# Goal feasibility: 1-6, but an ATTAINABILITY judgement rather than
# agreement — different anchors, so a different scale object. Sharing one
# would silently relabel the other.
LIKERT6_FEASIBLE = {
    "kind": "likert", "min": 1, "max": 6,
    "labels_fa": {1: "اصلاً امکان‌پذیر نیست", 6: "کاملاً امکان‌پذیر است"},
}

# EFT process items: 1-6 APPLICABILITY. Again not agreement.
LIKERT6_APPLIES = {
    "kind": "likert", "min": 1, "max": 6,
    "labels_fa": {1: "اصلاً صدق نمی‌کند", 6: "کاملاً صدق می‌کند"},
}

FREE_TEXT = {"kind": "text", "multiline": True}


# ── sources ─────────────────────────────────────────────────────────────
INSTRUMENTALITY_SOURCE = (
    "Perceived-instrumentality literature informed; Persian wording adapted "
    "for this study. NOT a validated Persian scale."
)

EFFORT_SOURCE = (
    "Intended-effort / L2 motivational-self-system literature informed; "
    "Persian wording adapted for this study. NOT a validated Persian scale."
)

EFT_PROCESS_SOURCE = (
    "Episodic future thinking phenomenology (vividness, concreteness, detail, "
    "clarity, pre-experiencing); Persian wording written for this study."
)

HCI_SOURCE = "Study-specific HCI evaluation item"

TRANSLATED_ADAPTED = "translated_and_adapted_for_current_study"
AUTHORED = "original_wording_authored_in_persian"


def _item(code, instrument, phase, timepoint_role, text_fa, text_en, scale,
          source, measure_status, *, translation_status=AUTHORED,
          reverse=False, helper_fa="", notes=""):
    """One item, carrying everything needed to interpret it later.

    `timepoint_role` is 'pre', 'post', 'both' or 'once' — documentation for a
    reader; which timepoint actually serves it is decided by TIMEPOINTS.
    """
    return {
        "code": code,
        "instrument": instrument,
        "phase": phase,
        "group_visibility": "both",
        "timepoint_role": timepoint_role,
        "text_fa": text_fa,
        "helper_fa": helper_fa,
        "text_en": text_en,
        "source_en": text_en,
        "scale": scale,
        "response_type": scale["kind"],
        "scale_min": scale.get("min"),
        "scale_max": scale.get("max"),
        "scale_labels": scale.get("labels_fa", {}),
        "reverse": reverse,
        "source": source,
        "publication_type": None,
        "measure_status": measure_status,
        "validated": False,
        "validated_status": False,
        "translation_status": translation_status,
        "battery_version": BATTERY_VERSION,
        "notes": notes,
    }


# ════════════════════════════════════════════════════════════════════════
# PHASE 1 — the participant's future goal
# ════════════════════════════════════════════════════════════════════════
# Collected BEFORE the pre-questionnaire, because the PI items ask the
# participant to answer "thinking about this same future goal" — without the
# goal already in hand those items have no referent.
#
# This same text is then seeded into the chatbot as its `goal`, so nobody is
# asked to invent a second future.
FUTURE_GOAL = [
    _item(
        "future_goal", "future_goal", 1, "once",
        "یک هدف آینده‌ی شخصی را در نظر بگیر که کار پژوهشی و درس روش تحقیق "
        "برای رسیدن به آن اهمیت دارد. این هدف می‌تواند مربوط به دفاع از "
        "پایان‌نامه، فارغ‌التحصیل شدن، چاپ مقاله، ارائه‌ی نتیجه‌ها در "
        "کنفرانس، ادامه‌ی تحصیل، یا هر هدف دیگری باشد که برای خودت مهم است.",
        "Think of a personal future goal for which your research work and your "
        "research-methods course matter.",
        FREE_TEXT, HCI_SOURCE, STUDY_HCI,
        helper_fa="هدف آینده‌ی من: …",
        notes=("The single canonical goal. Displayed above the PI items at "
               "pre and post, and seeded into the EFT chatbot so the "
               "participant is never asked for a second goal."),
    ),
]


# ════════════════════════════════════════════════════════════════════════
# PHASE 2 — PRE only: goal feasibility
# ════════════════════════════════════════════════════════════════════════
# Contextual/descriptive. Not part of any primary score, and asked only at
# pre — a post measurement would invite the participant to report change they
# think the session was supposed to produce.
GOAL_FEASIBILITY = [
    _item(
        "goal_feasibility_pre", "goal_feasibility", 2, "pre",
        "در حال حاضر، تا چه حد فکر می‌کنی رسیدن به این هدف برایت امکان‌پذیر "
        "است؟",
        "Right now, how attainable do you think reaching this goal is for you?",
        LIKERT6_FEASIBLE, HCI_SOURCE, STUDY_HCI,
        notes="Contextual/descriptive only. PRE only, by design.",
    ),
]


# ════════════════════════════════════════════════════════════════════════
# Perceived Instrumentality — PRE and POST, identical wording
# ════════════════════════════════════════════════════════════════════════
# Built once and emitted twice with a _pre / _post suffix. Generating both
# from one list is what guarantees the two administrations are word-for-word
# identical: a pre/post comparison where the wording drifted is measuring the
# wording, not the intervention.
_PI = [
    ("1", "من برای پیش بردن کار پژوهشی‌ام تلاش می‌کنم، چون پیشرفت من در این "
          "کار در رسیدن به این هدف آینده نقش دارد.",
     "I make an effort on my research because my progress in it plays "
     "a part in reaching this future goal."),
    ("2", "من برای پیش بردن کار پژوهشی‌ام تلاش می‌کنم، چون پیشرفت من در این "
          "کار برای رسیدن به آینده‌ای که برای خودم می‌خواهم مهم است.",
     "I make an effort on my research because my progress in it "
     "matters for reaching the future I want for myself."),
    ("3", "من برای پیش بردن کار پژوهشی‌ام تلاش می‌کنم، چون این کار برای تبدیل "
          "شدن به فردی که در این آینده می‌خواهم باشم مهم است.",
     "I make an effort on my research because it matters for "
     "becoming the person I want to be in that future."),
    ("4", "من برای پیش بردن کار پژوهشی‌ام تلاش می‌کنم، چون این کار در رسیدن "
          "به این هدف آینده نقش دارد.",
     "I make an effort on my research because it plays a part "
     "in reaching this future goal."),
    ("5", "من برای پیش بردن کار پژوهشی‌ام تلاش می‌کنم، چون این کار برای رسیدن "
          "به آینده‌ای که برای خودم می‌خواهم مهم است.",
     "I make an effort on my research because it matters for "
     "reaching the future I want for myself."),
]

_IE = [
    ("1", "مایلم زمان زیادی را صرف کار پژوهشی‌ام کنم.",
     "I am willing to spend a lot of time on my research."),
    ("2", "حتی اگر مجبور به انجام کار پژوهشی نباشم، مایلم به ادامه‌ی آن "
          "بپردازم.",
     "Even if I were not required to do my research, I would want to keep "
     "going with it."),
    ("3", "مایلم بیش از موضوعات دیگر روی کار پژوهشی‌ام تمرکز کنم.",
     "I am willing to focus on my research more than on other subjects."),
    ("4", "اگر در آینده دوره‌ای درباره‌ی روش تحقیق ارائه شود، مایلم در آن "
          "شرکت کنم.",
     "If a course on research methods were offered in the future, I would "
     "want to take it."),
    ("5", "اگر یک فعالیت یا تمرین اختیاری برای کار پژوهشی در دسترس باشد، "
          "مایلم آن را انجام دهم.",
     "If an optional research activity or exercise were available, I would "
     "want to do it."),
    ("6", "آماده‌ام برای کار پژوهشی تلاش زیادی صرف کنم.",
     "I am ready to put a lot of effort into my research."),
]


def _pi(suffix: str, phase: int):
    return [
        _item(f"pi{n}_{suffix}", "perceived_instrumentality", phase,
              suffix, fa, en, LIKERT5_AGREE, INSTRUMENTALITY_SOURCE,
              PUBLISHED_ADAPTED, translation_status=TRANSLATED_ADAPTED,
              notes=("Perceived Instrumentality item " + n + ". Answered "
                     "while looking at the participant's own future goal, "
                     "which the page displays above these items."))
        for n, fa, en in _PI
    ]


def _ie(suffix: str, phase: int):
    return [
        _item(f"ie{n}_{suffix}", "intended_effort", phase, suffix, fa, en,
              LIKERT6_AGREE, EFFORT_SOURCE, PUBLISHED_ADAPTED,
              translation_status=TRANSLATED_ADAPTED,
              notes="Intended Effort item " + n + ".")
        for n, fa, en in _IE
    ]


PI_PRE, PI_POST = _pi("pre", 2), _pi("post", 5)
IE_PRE, IE_POST = _ie("pre", 2), _ie("post", 5)


# ════════════════════════════════════════════════════════════════════════
# PHASE 5 — POST only: how the imagining itself went
# ════════════════════════════════════════════════════════════════════════
# Asks only about the ACT of imagining, never whether the imagined future is
# likely — which is what keeps it safe for participants who find their future
# genuinely uncertain.
#
# Store item-level. Do NOT average these into a single "EFT score" and
# present it as validated; nothing here has been validated in Persian.
EFT_PROCESS = [
    _item("eft_vividness", "eft_process", 5, "post",
          "تصویر صحنه‌ی آینده در ذهنم زنده و واضح بود.",
          "The image of the future scene in my mind was vivid and clear.",
          LIKERT6_APPLIES, EFT_PROCESS_SOURCE, STUDY_HCI),
    _item("eft_concreteness", "eft_process", 5, "post",
          "صحنه‌ای که تصور کردم مشخص و عینی بود.",
          "The scene I imagined was specific and concrete.",
          LIKERT6_APPLIES, EFT_PROCESS_SOURCE, STUDY_HCI),
    _item("eft_detail", "eft_process", 5, "post",
          "صحنه‌ی آینده را با جزئیات تصور کردم.",
          "I imagined the future scene in detail.",
          LIKERT6_APPLIES, EFT_PROCESS_SOURCE, STUDY_HCI),
    _item("eft_clarity", "eft_process", 5, "post",
          "آنچه در صحنه‌ی آینده اتفاق می‌افتاد برایم روشن بود.",
          "What was happening in the future scene was clear to me.",
          LIKERT6_APPLIES, EFT_PROCESS_SOURCE, STUDY_HCI),
    _item("eft_simulated_experience", "eft_process", 5, "post",
          "هنگام تصور این صحنه، احساس می‌کردم انگار واقعاً در حال تجربه‌ی آن "
          "هستم.",
          "While imagining this scene, I felt as if I were actually "
          "experiencing it.",
          LIKERT6_APPLIES, EFT_PROCESS_SOURCE, STUDY_HCI),
]


# ════════════════════════════════════════════════════════════════════════
# PHASE 5 — POST only: experience evaluation
# ════════════════════════════════════════════════════════════════════════
# Evaluates the ARTIFACT and the experience, not the participant. The last
# three are deliberately negative: a battery that only offers ways to say the
# system worked will collect exactly that, and the discomfort item is also an
# ethical check, not just a design one.
HCI_EVAL = [
    _item("hci_personal_meaning", "hci_eval", 5, "post",
          "این صحنه برای من شخصاً معنادار بود.",
          "This scene was personally meaningful to me.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI),
    _item("hci_text_match", "hci_eval", 5, "post",
          "متن تولیدشده با چیزی که در ذهن داشتم هماهنگ بود.",
          "The generated text matched what I had in mind.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI),
    _item("hci_image_match", "hci_eval", 5, "post",
          "تصویر تولیدشده با چیزی که در ذهن داشتم هماهنگ بود.",
          "The generated image matched what I had in mind.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI),
    _item("hci_ease", "hci_eval", 5, "post",
          "انجام مراحل این تجربه برای من آسان بود.",
          "Going through the steps of this experience was easy for me.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI),
    _item("hci_ownership", "hci_eval", 5, "post",
          "احساس می‌کردم این آینده متعلق به خودم است، نه اینکه سیستم آن را "
          "برای من تعیین کرده باشد.",
          "I felt this future was my own, rather than something the system "
          "decided for me.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI),
    _item("hci_emotional_burden", "hci_eval", 5, "post",
          "بخشی از این تجربه برای من از نظر احساسی سنگین یا ناراحت‌کننده بود.",
          "Some part of this experience was emotionally heavy or upsetting "
          "for me.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI, reverse=True,
          notes=("Negatively worded — a HIGH score is a worse outcome. Also "
                 "an ethical check: imagining a future one may not reach can "
                 "be uncomfortable, and the study should be able to see that "
                 "rather than only collect ways of saying it went well.")),
    _item("hci_pressure_to_believe", "hci_eval", 5, "post",
          "احساس کردم سیستم از من می‌خواهد باور کنم این آینده حتماً اتفاق "
          "خواهد افتاد.",
          "I felt the system wanted me to believe this future would "
          "definitely happen.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI, reverse=True,
          notes=("Negatively worded. Checks the instruction's own claim that "
                 "the participant need not believe the future will happen.")),
    _item("hci_unrealistic", "hci_eval", 5, "post",
          "بخشی از صحنه برای شرایط واقعی من نامرتبط یا غیرواقعی به نظر "
          "می‌رسید.",
          "Part of the scene seemed irrelevant or unrealistic for my actual "
          "circumstances.",
          LIKERT6_AGREE, HCI_SOURCE, STUDY_HCI, reverse=True,
          notes=("Negatively worded. The closest thing to a fidelity check on "
                 "the generated cue, which is otherwise unverified.")),
]


OPEN_FEEDBACK = [
    _item("feedback_mismatch", "open_feedback", 5, "post",
          "آیا بخشی از متن، تصویر یا گفت‌وگو با چیزی که در ذهن داشتی هماهنگ "
          "نبود؟ اگر بله، لطفاً کوتاه توضیح بده.",
          "Was any part of the text, image or conversation out of step with "
          "what you had in mind? If so, please explain briefly.",
          FREE_TEXT, HCI_SOURCE, STUDY_OPEN,
          notes="Optional."),
    _item("feedback_connection_change", "open_feedback", 5, "post",
          "این تجربه چه تغییری، اگر تغییری، در ارتباطی که میان کار پژوهشی و "
          "آینده‌ی خود احساس می‌کنی ایجاد کرد؟",
          "What change, if any, did this experience make to the connection "
          "you feel between your research work and your own future?",
          FREE_TEXT, HCI_SOURCE, STUDY_OPEN,
          notes="Optional."),
]


# ── what is asked when ──────────────────────────────────────────────────
# `show_goal` puts the participant's own future goal on screen above the
# items. The PI wording refers to "this future goal", so without it those
# items have no referent on the page.
TIMEPOINTS: dict[str, dict] = {
    "future_goal": {"phase": 1, "items": FUTURE_GOAL, "show_goal": False},
    "pre": {"phase": 2, "items": GOAL_FEASIBILITY + PI_PRE + IE_PRE,
            "show_goal": True},
    "post": {"phase": 5,
             "items": PI_POST + IE_POST + EFT_PROCESS + HCI_EVAL
                      + OPEN_FEEDBACK,
             "show_goal": True},
}

# Items a participant may leave blank. Everything else is required before the
# page will submit.
OPTIONAL_CODES = {i["code"] for i in OPEN_FEEDBACK}

GOAL_PROMPT_FA = "هنگام پاسخ دادن، به همین هدف آینده فکر کن:"

SOURCE_NOTE = (
    f"Active battery: {BATTERY_VERSION}. "
    "ADAPTED, published-informed — pi1-5 and ie1-6 (perceived instrumentality "
    "and intended effort; Persian wording adapted for this study). "
    "STUDY-SPECIFIC — future_goal, goal_feasibility_pre, eft_* and hci_*. "
    "STUDY-SPECIFIC OPEN-ENDED — feedback_*. "
    "No item has a validated Persian version; all Persian wording is a "
    "translation or original study wording and must be reported as such."
)


# ════════════════════════════════════════════════════════════════════════
# DEPRECATED — retained so historical rows stay interpretable
# ════════════════════════════════════════════════════════════════════════
# These codes exist in already-collected data from earlier protocol versions.
# They are NOT in TIMEPOINTS and can never be served.
DEPRECATED_ITEMS: dict[str, str] = {
    "goal_importance": "Asked inside the EFT chatbot; superseded as a battery item by future_goal + goal_feasibility_pre.",
    "task_goal_connection_1": "Reading-task protocol. No reading task in this version.",
    "task_goal_connection_2": "Reading-task protocol.",
    "task_goal_connection_3": "Reading-task protocol.",
    "intended_study_time": "Reading-task protocol. Superseded by the Intended Effort block.",
    "control_english_goal": "Control arm's goal form. No control arm in this version.",
    "control_goal_domain": "Control arm's goal form.",
    "control_skill_focus": "Control arm's goal form.",
    "control_goal_horizon": "Control arm's goal form.",
    "cue_fidelity": "Superseded by hci_text_match / hci_image_match.",
    "cue_personal_meaning": "Superseded by hci_personal_meaning.",
    "fsc_similarity": "Future Self-Continuity circles. Not in this version.",
    "fsc_connected": "Future Self-Continuity circles. Not in this version.",
    **{f"reminder_{k}": "Scheduled-reminder protocol. No reminders in this version."
       for k in ("helpfulness", "disruption", "timing", "future_use",
                 "relevance", "goal_connection", "helped", "distracted")},
    **{f"eft_imagery_{k}": "Asayama imagery check. Superseded by the eft_* process items."
       for k in ("vivid", "specific", "detail", "clear", "preexperience")},
    **{f"tipi_{i}": "TIPI. No filler inventory in this version." for i in range(1, 11)},
    **{f"sus_{i}": "System Usability Scale. Not in this version." for i in range(1, 11)},
    **{f"intent_{k}": "Old baseline intention battery." for k in ("hours", "sessions", "confidence")},
}

# The PREVIOUS battery, kept so historical rows stay interpretable.
#
# The pi*/ie* item CODES are unchanged — only the wording changed (English
# learning → research work). So the codes below CANNOT be marked deprecated:
# they are the same items, re-worded for a new population, and every row
# already carries the battery_version it was collected under.
#
# What that means for analysis: a pi1_pre answer collected under
# `eft_visualization_v1` asked about English, and one collected under
# `research_methods_v1` asked about the participant's research. They are not
# the same measurement. The export carries `battery_version` on every row
# precisely so they are never pooled by accident.
PREVIOUS_BATTERY_VERSIONS = {
    "eft_visualization_v1": (
        "Previous battery: the same pi1-5 / ie1-6 items worded around "
        "LEARNING ENGLISH rather than research work. Not comparable with "
        "research_methods_v1 and must not be pooled with it."
    ),
}


def items_for(timepoint: str, study_group: str | None = None) -> list[dict]:
    """Items due at this timepoint, in protocol order.

    `study_group` is accepted and ignored: this version has a single
    participant path. The parameter stays so existing callers keep working.
    """
    spec = TIMEPOINTS.get(timepoint)
    return list(spec["items"]) if spec else []


def shows_goal(timepoint: str) -> bool:
    spec = TIMEPOINTS.get(timepoint)
    return bool(spec and spec.get("show_goal"))


def item_by_code(code: str) -> dict | None:
    for spec in TIMEPOINTS.values():
        for item in spec["items"]:
            if item["code"] == code:
                return item
    return None


ALL_ITEMS = [i for spec in TIMEPOINTS.values() for i in spec["items"]]
