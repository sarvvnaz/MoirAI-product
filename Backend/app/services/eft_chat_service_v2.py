"""Guided EFT chatbot (work step 12) — the 7-question format.

Design:
  - The BACKEND owns progress and pacing (which question is active, what's
    collected, WHEN the next question is asked). The LLM's only job each
    turn is: (1) judge if the answer is vivid enough, (2) extract a clean
    version of the answer, (3) write a short, warm one-line acknowledgment.
    The backend ALWAYS appends the next question deterministically right
    after — this guarantees the flow never stalls waiting on the LLM to
    remember to ask it.
  - Vividness probing is capped at ONE follow-up per question so the
    participant never gets tired.
  - After all 7 answers are in, the summary is shown IMMEDIATELY — the only
    thing ever asked at the end is confirm-or-edit. Editing appends the
    participant's addition to the previous answer (no re-asking, no probing)
    and returns straight to confirm.
  - Memory: conversation history + collected answers persist in the existing
    EFTChatState row (fields_json), so a page reload continues the chat.
  - The intro is FIXED text (not LLM output): short, friendly, explains the
    assignment with an example from a different context (a runner imagining
    race morning), because participants arrive confused.
  - Fallback without an OpenAI key: canned questions, accept any non-trivial
    answer — the study never blocks.

API result shape (consumed by the Flutter chat page):
  {
    "bot": str,
    "needs_user": bool,
    "can_start_session": bool,      # true after final confirmation
    "question_index": int,          # 0..6 active question, 7 = confirm stage
    "collected": [bool x 7],        # drives the checklist UI
    "episode_summary": str | None,
  }
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import CHAT_MODEL, openai_client
from app.database import models

# The 7 EFT questions — single source of truth (order matters; keys match
# image_service._EPISODE_KEYS). Each anchors the participant in the SAME
# imagined future scene so the answers stay coherent enough to build an image.
#
# THE AUDIENCE: students in a research-methods course. Their distal goal is
# ACADEMIC — finishing the research, defending it, graduating. So the scene
# the questions build is the day of the defence, the defence, the moment the
# supervisor says yes, the graduation hall. That is the same mechanism as
# before (a concrete, personally-meaningful future moment) pointed at a
# different goal.
#
# Each question uses the FIXED generic anchor («وقتی به هدفت رسیدی») —
# never the participant's own goal text (that made questions convoluted).
# Each question also carries a light option-guide (general directions, not
# answers) so the participant is never confused about what kind of answer
# fits — mirroring how the time question offers "months? morning/evening?".
QUESTIONS: List[Dict[str, str]] = [
    {"key": "goal",
     "short": "هدف",
     "zoom": "distal goal — the abstract ambition, widest level of the zoom",
     "text": "بیا از چیزی شروع کنیم که برات مهمه: کاری که می‌خوای روش وقت بذاری، "
             "به کدوم هدف بلندمدتت کمک می‌کنه؟ 🎯\n"
             "می‌تونه رشد در کار، تحصیل، یک پروژه‌ی شخصی یا هر چیزی باشه که خودت می‌خوای."},
    {"key": "when",
     "short": "زمان",
     # Still the single most important narrowing step — a period of life is
     # semantic, one moment is episodic. But it is asked as "how far away,
     # and what time of day": naming a time of day lands the participant in a
     # single moment on its own, without a rule to follow. Explaining the
     # 24-hour constraint made people stop and work out whether their idea
     # qualified, which is the opposite of imagining.
     "zoom": "temporal window, narrowed to ONE moment via time of day",
     "text": "اون لحظه‌ای که به هدفت رسیدی رو کی تصور می‌کنی؟ چند وقت دیگه‌ست و چه وقتِ روزه؟"},
    {"key": "where",
     "short": "مکان",
     "zoom": "five-field schema: the precise setting of that single day",
     "text": "توی اون لحظه کجایی؟ مثلاً خونه، محل کار یا جای دیگه‌ای که توی ذهنته."},
    {"key": "action",
     "short": "کار",
     "zoom": "five-field schema: the main action, narrated in present tense",
     "text": "توی اون لحظه داری چه کاری انجام می‌دی؟"},
    {"key": "objects",
     "short": "اطراف",
     "zoom": "five-field schema: tangible objects that anchor the scene",
     "text": "یکی دو تا چیز که اونجا دور و برت می‌بینی چیه؟"},
    {"key": "who",
     "short": "افراد",
     "zoom": "five-field schema: specific people present",
     "text": "توی اون لحظه تنهایی یا کسی هم کنارت هست؟"},
    {"key": "feeling",
     "short": "احساس",
     "zoom": "five-field schema: emotion — closes the loop back to the goal",
     "text": "وقتی خودت رو توی اون لحظه تصور می‌کنی، چه حسی داری؟"},
]

# Importance of the distal goal, 1–6 (Rosenbaum et al.: personal importance
# strengthens diachronic identity — the sense that today's self is the same
# person who benefits later). Asked as a ONE-TAP chip row in the UI right
# after the goal answer, deliberately NOT a typed turn: these participants
# tire quickly and this is a rating, not an imagining task.
#
# THIS IS THE CANONICAL WORDING of the shared goal_importance item. The
# control arm's questionnaire copy is derived FROM here, not the other way
# round — see measure_items.GOAL_IMPORTANCE, which mirrors this question and
# these anchors so the two arms answer the same thing. A test pins them
# together. Change this and the control form must follow.
#
# Kept OUT of QUESTIONS on purpose — `collected[]`, the checklist UI and
# image_service._EPISODE_KEYS all assume exactly 7 entries.
IMPORTANCE_KEY = "importance"
IMPORTANCE_MIN = 1
IMPORTANCE_MAX = 6
IMPORTANCE_PROMPT = (
    "قبل از اینکه بریم جلوتر، یه سوال کوتاه: رسیدن به این هدف چقدر برات مهمه؟\n"
    "از ۱ (خیلی کم) تا ۶ (خیلی زیاد) یکی رو انتخاب کن."
)
IMPORTANCE_ACK = "ممنون 🌱 حالا بریم سراغ اون لحظه."


def question_text(qi: int, fields: Dict[str, Any]) -> str:
    # fields kept in the signature so call sites stay unchanged.
    return QUESTIONS[qi]["text"]

CONFIRM_WORDS = ["تایید", "تأیید", "yes", "ok", "باشه", "درسته", "خوبه"]
EDIT_WORDS = ["ویرایش", "اصلاح", "تغییر", "edit"]

# Short on purpose. The previous version said the right things at a length
# nobody in a hurry reads, and an intro that gets skipped does nothing — so
# the same points are made in a quarter of the words, with the one line that
# matters most flagged at the top.
INTRO = (
    " لطفاً این چند خط رو کامل بخون، رد کردنش کل تجربه رو سخت‌تر می‌کنه.\n\n"
    "قراره با هم یه روزِ مشخص از آینده‌ات رو پیدا کنیم؛ روزی که به "
    "هدفت — همون هدفی که توی این درس دنبالشی — رسیدی. قدم به قدم می‌پرسم، "
    "تو فقط تصور کن.\n\n"
    "• لازم نیست لحظه‌ی بزرگی باشه — یه روز معمولی توی مسیرت هم عالیه.\n"
    "• لازم نیست از آینده‌ات مطمئن باشی. دنبال پیش‌بینی نیستیم، دنبال یه "
    "تصویریم که بشه بهش فکر کرد.\n"
    "• اگه جایی گیر کردی، دکمه‌ی 💡  چند تا ایده بهت می‌ده. "
    "اون‌ها فقط راهنمان، حتماً عوضشون کن و از خودت و با جزییات بیشتر بگو، چون قراره تصویرِ "
    "*تو* ساخته بشه، نه یه تصویر عمومی.\n"
    "• هر سوال یا تردیدی داشتی همینجا بپرس؛.\n\n"
    "آخرش از روی حرف‌های خودت یه تصویر واقعی از اون روز می‌سازم — هر چی "
    "جزئی‌تر بگی، شخصی‌تر می‌شه. 🌿\n\n"
    + QUESTIONS[0]["text"]
)

FALLBACK_PROBE = "میشه یه کم بیشتر برام تعریف کنی؟ هر جزئیاتی که به ذهنت میاد به ساختن تصویرت کمک می‌کنه."

# The Inspire options. FIXED, identical for every participant, never
# generated.
#
# Two reasons they are broad rather than fully-formed scenes:
#   - A finished scene is not a spark, it is an answer. Handed «I'm speaking
#     for half an hour before class with a word list on my phone», a stuck
#     participant adopts it, and the episode — and the image built from it —
#     stops being theirs. These give a DIRECTION and leave the detail empty
#     so the participant still has to supply it.
#   - Three detailed options at once is a reading task on top of an
#     imagining task, for people who are already overwhelmed. Short lines
#     scan in a second.
#
# Generating them per turn also cost a model call every time someone got
# stuck — paid for, and waited on, to produce something a fixed list does
# better.
# Shown when the participant taps «الهام». STATIC for every step and every
# participant — never generated.
#
# Two reasons. Cost: this is the button a stuck person presses repeatedly, and
# it was firing a model call each time. And control: generated suggestions
# came back oddly specific ("at 8pm I record ten minutes of my own voice"),
# which is worse than useless here — a stuck participant adopts the example
# wholesale and the episode becomes the suggestion's, not theirs.
#
# So these are deliberately VAGUE: a direction to think in, not a scene to
# copy. No times, no named places, no props, no scripted actions. The
# participant still has to supply everything that makes it an episode.
FALLBACK_INSPIRE: Dict[str, List[str]] = {
    "goal": [
        "می‌خوام از پایان‌نامه‌ام دفاع کنم.",
        "می‌خوام پژوهشم چاپ بشه.",
        "می‌خوام دوره‌ام رو با موفقیت تموم کنم.",
    ],
    "when": [
        "آخر ترم، بهار، صبح.",
        "یه روز آخر هفته، تابستان، عصر.",
        "یه روز خاص — مثلاً روز دفاع.",
    ],
    "where": [
        "یه جای دانشگاهی — سالن دفاع، کلاس، یا اتاق اساتید.",
        "یه جای عمومی و شلوغ‌تر — همایش، کنفرانس، یا مراسم.",
        "یه جای آروم که خودت دوستش داری.",
    ],
    "action": [
        "دارم نتیجه‌های پژوهشم رو ارائه می‌دم.",
        "دارم یه بخش مهم از کارم رو توضیح می‌دم.",
        "دارم یه مدرک یا سند مهم رو توی دستم می‌گیرم.",
    ],
    "objects": [
        "چیزهایی که معمولاً موقع کار پژوهشی دورت هست.",
        "یه نوشیدنی و چند تا وسیله‌ی ساده.",
        "چیزی که از پنجره یا اطرافت دیده می‌شه.",
    ],
    "who": [
        "تنهام.",
        "یکی دو نفر که تازه باهاشون آشنا شدم.",
        "کسی که برام مهمه — دوست یا خانواده.",
    ],
    "feeling": [
        "آروم و بی‌استرس.",
        "مطمئن به خودم.",
        "سبک و راضی.",
    ],
}

# CHAT_MODEL + the provider base URL live in app/config.py — see there to
# switch model or point the app at an OpenAI-compatible gateway.


class EFTChatServiceV2:
    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id
        self._client = openai_client()

    # ── state helpers ──────────────────────────────────────────
    def _get_or_create_state(self) -> models.EFTChatState:
        state = (
            self.db.query(models.EFTChatState)
            .filter(models.EFTChatState.user_id == self.user_id)
            .first()
        )
        if state is None:
            state = models.EFTChatState(
                user_id=self.user_id, current_step=0, fields_json="{}")
            self.db.add(state)
            self.db.flush()
        return state

    def reset_state(self) -> models.EFTChatState:
        state = self._get_or_create_state()
        state.current_step = 0
        state.fields_json = "{}"
        state.last_updated = datetime.utcnow()
        self.db.flush()
        return state

    @staticmethod
    def _fields(state: models.EFTChatState) -> Dict[str, Any]:
        try:
            return json.loads(state.fields_json or "{}")
        except Exception:
            return {}

    def _save(self, state: models.EFTChatState, fields: Dict[str, Any],
              question_index: int) -> None:
        state.current_step = question_index
        state.fields_json = json.dumps(fields, ensure_ascii=False)
        state.last_updated = datetime.utcnow()
        self.db.flush()

    # ── result assembly ────────────────────────────────────────
    def _result(self, bot: str, fields: Dict[str, Any], qi: int,
                needs_user: bool = True, can_start: bool = False,
                summary: Optional[str] = None,
                awaiting_importance: bool = False) -> Dict[str, Any]:
        collected = [bool(fields.get(q["key"])) for q in QUESTIONS]
        return {
            "bot": bot,
            "needs_user": needs_user,
            "can_start_session": can_start,
            "question_index": qi,
            "collected": collected,
            "episode_summary": summary,
            # When true the UI shows the 1-6 chip row and hides the text input:
            # this step is a rating, not something to type.
            "awaiting_importance": awaiting_importance,
            "importance": fields.get(IMPORTANCE_KEY),
            "importance_range": [IMPORTANCE_MIN, IMPORTANCE_MAX],
        }

    def _needs_importance(self, fields: Dict[str, Any]) -> bool:
        """Rating is due once the distal goal exists and nothing is rated yet."""
        # Research importance rating paused for the product.
        # return bool(fields.get("goal")) and not fields.get(IMPORTANCE_KEY)
        return False

    def _store_importance(self, state, fields, value: int) -> Dict[str, Any]:
        """Record the 1-6 rating, then continue into the next question."""
        fields[IMPORTANCE_KEY] = max(IMPORTANCE_MIN, min(IMPORTANCE_MAX, int(value)))
        next_qi = next(
            (i for i, x in enumerate(QUESTIONS) if not fields.get(x["key"])),
            len(QUESTIONS),
        )
        if next_qi >= len(QUESTIONS):
            self._save(state, fields, next_qi)
            return self._confirm_stage(state, fields, "")
        history: List[Dict[str, str]] = fields.get("_history", [])
        bot = f"{IMPORTANCE_ACK}\n\n{question_text(next_qi, fields)}"
        history.append({"role": "assistant", "content": bot})
        fields["_history"] = history[-16:]
        self._save(state, fields, next_qi)
        return self._result(bot, fields, next_qi)

    # ── main turn handler ──────────────────────────────────────
    def process_message(self, message: Optional[str],
                        reset: bool = False,
                        importance: Optional[int] = None) -> Dict[str, Any]:
        state = self.reset_state() if reset else self._get_or_create_state()
        fields = self._fields(state)
        qi = int(state.current_step)
        msg = (message or "").strip()

        # Importance chip tapped.
        if importance is not None:
            return self._store_importance(state, fields, importance)

        # Rating still outstanding — hold here rather than letting a typed
        # message be mistaken for the answer to the next question.
        if self._needs_importance(fields) and qi < len(QUESTIONS):
            return self._result(IMPORTANCE_PROMPT, fields, qi,
                                awaiting_importance=True)

        # First contact / empty ping → fixed intro (+ resume support).
        if not msg:
            if qi == 0 and not fields.get(QUESTIONS[0]["key"]):
                return self._result(INTRO, fields, 0)
            # Resume at the first UNANSWERED question (never a done one).
            resume_qi = next(
                (i for i, x in enumerate(QUESTIONS)
                 if not fields.get(x["key"])),
                len(QUESTIONS),
            )
            if resume_qi >= len(QUESTIONS):
                return self._confirm_stage(state, fields, "")
            self._save(state, fields, resume_qi)
            resume = ("خوش برگشتی! از همینجا ادامه بدیم 🌱\n"
                      f"{question_text(resume_qi, fields)}")
            return self._result(resume, fields, resume_qi)

        # Confirm/edit stage.
        if qi >= len(QUESTIONS):
            return self._confirm_stage(state, fields, msg)

        # Normal question turn.
        return self._question_turn(state, fields, qi, msg)

    # ── question collection ────────────────────────────────────
    def _question_turn(self, state, fields, qi, msg) -> Dict[str, Any]:
        q = QUESTIONS[qi]
        probed_key = f"_probed_{q['key']}"
        history: List[Dict[str, str]] = fields.get("_history", [])
        history.append({"role": "user", "content": msg})

        decision = self._llm_turn(fields, qi, history,
                                  already_probed=bool(fields.get(probed_key)))

        reply = (decision.get("reply") or "").strip()
        status = decision.get("question_status") or "collected"
        extracted = (decision.get("extracted_answer") or "").strip()
        next_question = (decision.get("next_question") or "").strip()
        print(f"🤖 chat q{qi} status={status} reply={reply[:60]!r}")

        # HARD RULE: a non-collected turn must END WITH A QUESTION, or the
        # participant is left staring at a statement with nothing to answer.
        # The LLM sometimes returns needs_more/off_topic with an ack-style
        # reply and no question — the backend repairs that here.
        def ensure_question(text: str, fallback_q: str) -> str:
            if "؟" in text or "?" in text:
                return text
            return f"{text}\n{fallback_q}".strip()

        # LLM call failed. Stay on the step and re-ask — never store an
        # unvalidated turn (see _llm_turn's failure return).
        if status == "llm_error":
            bot = ensure_question(
                "ببخشید، یه لحظه ارتباطم قطع شد 🙏 دوباره می‌پرسم:",
                question_text(qi, fields))
            history.append({"role": "assistant", "content": bot})
            fields["_history"] = history[-16:]
            self._save(state, fields, qi)
            return self._result(bot, fields, qi)

        # Off-topic: a question, a doubt, or something unrelated to THIS step.
        # The LLM has already answered it substantively; we just make sure the
        # turn ends with the step's question again.
        #
        # This NEVER falls through to collection. It used to: after three
        # off-topic turns the code stored the participant's message as the
        # answer — and since off_topic sets extracted_answer to null, what got
        # stored was their confusion itself ("I don't know what you mean")
        # recorded as, say, their `where`, with the step marked done. A
        # confused participant was exactly the one whose episode got corrupted.
        # Repetition is now handled by escalating help instead.
        if status == "off_topic":
            offkey = f"_offtopic_{q['key']}"
            fields[offkey] = int(fields.get(offkey, 0)) + 1
            if not reply:
                reply = "بذار با هم روشنش کنیم 🙂"
            if fields[offkey] >= 3:
                # Stuck. Stop re-asking the same way and offer a concrete way
                # out rather than pretending the step is answered.
                reply = (f"{reply}\n\nاگه سخته که خودت شروع کنی، دکمه‌ی "
                         "«الهام بگیر» چند تا نمونه‌ی کوتاه بهت می‌ده که "
                         "می‌تونی تغییرشون بدی. یا اگه ترجیح می‌دی، فقط یه "
                         "کلمه بنویس و من از همونجا ادامه می‌دم.")
            reply = ensure_question(reply, question_text(qi, fields))
            history.append({"role": "assistant", "content": reply})
            fields["_history"] = history[-16:]
            self._save(state, fields, qi)
            return self._result(reply, fields, qi)

        if status == "needs_more" and not fields.get(probed_key):
            # One detail probe max per question. The LLM's reply here IS the
            # follow-up (referencing their own words) — no deterministic
            # question follows, so it must itself ask something.
            fields[probed_key] = True
            if not reply:
                reply = FALLBACK_PROBE
            # Keep the clarification on the active step, regardless of model drift.
            probes = {
                'goal': 'دوست داری در بلندمدت به چی برسی؟',
                'when': 'اون لحظه رو چه زمانی تصور می‌کنی؟',
                'where': 'توی اون لحظه دقیقاً کجایی؟',
                'action': 'اونجا داری چه کاری انجام می‌دی؟',
                'objects': 'یکی دو تا چیز که اطرافت می‌بینی چیه؟',
                'who': 'کسی هم کنارت هست یا تنهایی؟',
                'feeling': 'توی اون لحظه چه حسی داری؟',
            }
            reply = probes[q['key']]
            history.append({"role": "assistant", "content": reply})
            fields["_history"] = history[-16:]
            self._save(state, fields, qi)
            return self._result(reply, fields, qi)

        # Collect (either LLM said collected, or probe budget exhausted).
        # The LLM sees the full history, so extracted_answer already merges
        # the first answer with any probe enrichment. Fall back to their raw
        # message only when the LLM gave us nothing usable — a 'collected'
        # status with an empty extraction still means they said something
        # on-topic, so their own words are the safe thing to keep.
        fields[q["key"]] = extracted or msg

        # Jump to the FIRST UNANSWERED question — not blindly qi+1. This is
        # what prevents re-asking already-answered questions after a field
        # was reopened by the review/edit/readiness paths.
        next_qi = next(
            (i for i, x in enumerate(QUESTIONS) if not fields.get(x["key"])),
            len(QUESTIONS),
        )

        # Acknowledgment (LLM, short) + the next step. The backend still owns
        # WHICH step comes next; the LLM only owns its WORDING, so the flow
        # can never stall on the LLM forgetting to ask. When it returns no
        # next_question — or one that isn't a question — we fall back to the
        # canned text, which is why the flow stays deterministic.
        ack = f"{reply} " if reply else ""

        # The distal goal is in — rate its importance before zooming in on a
        # moment. High personal importance is what ties today's self to the
        # future one, so it is asked while the goal is still the live topic.
        if self._needs_importance(fields):
            bot = f"{ack}{IMPORTANCE_PROMPT}".strip()
            history.append({"role": "assistant", "content": bot})
            fields["_history"] = history[-16:]
            self._save(state, fields, next_qi)
            return self._result(bot, fields, next_qi, awaiting_importance=True)

        if next_qi < len(QUESTIONS):
            canned = question_text(next_qi, fields)
            # The active step owns its question. Do not echo generated scene prose.
            bot = canned
            history.append({"role": "assistant", "content": bot})
            fields["_history"] = history[-16:]
            self._save(state, fields, next_qi)
            return self._result(bot, fields, next_qi)

        # All answered → straight to the review. NO extra questions at the
        # end: the only thing asked after the 7th answer is confirm-or-edit.
        return self._after_last_answer(state, fields, ack, history)

    def _after_last_answer(self, state, fields, ack, history) -> Dict[str, Any]:
        summary = self._review_text(fields)
        fields["_summary"] = summary
        bot = (f"{ack}این هم خلاصه‌ی چیزهایی که گفتی:\n\n{summary}\n\n"
               "می‌خوای بخشی رو کامل‌تر کنی؟ اگه بخوای چیزی اضافه یا عوض کنی "
               "بنویس «ویرایش». اگه همین خوبه، بنویس «تایید».").strip()
        history.append({"role": "assistant", "content": bot})
        fields["_history"] = history[-16:]
        self._save(state, fields, len(QUESTIONS))
        return self._result(bot, fields, len(QUESTIONS), summary=summary)

    # ── confirm / edit stage ───────────────────────────────────
    def _confirm_stage(self, state, fields, msg) -> Dict[str, Any]:
        summary = fields.get("_summary") or self._review_text(fields)

        if not msg:
            bot = (f"{summary}\n\nمی‌خوای چیزی رو کامل‌تر کنی؟ «تایید» یا «ویرایش»؟")
            return self._result(bot, fields, len(QUESTIONS), summary=summary)

        # Mid-edit: they just told us WHAT to add to the chosen part. Their
        # message IS the content — append it to the previous answer, done.
        # (An exact confirm word still confirms instead of being appended.)
        append_key = fields.get("_append_key")
        if append_key and msg not in CONFIRM_WORDS:
            old = (fields.get(append_key) or "").strip()
            fields[append_key] = f"{old}، {msg}" if old else msg
            fields.pop("_append_key", None)
            summary = self._review_text(fields)
            fields["_summary"] = summary
            self._save(state, fields, len(QUESTIONS))
            bot = (f"اضافه شد ✅ این هم خلاصه‌ی به‌روز شده:\n\n{summary}\n\n"
                   "اگه همین خوبه بنویس «تایید»؛ اگه بازم می‌خوای چیزی اضافه "
                   "کنی بنویس «ویرایش».")
            return self._result(bot, fields, len(QUESTIONS), summary=summary)

        if any(w in msg for w in CONFIRM_WORDS):
            bot = ("عالیه، تصویر آینده‌ات قفل شد ✅\n"
                   "چند لحظه چشم‌هاتو ببند و اون لحظه رو حس کن... "
                   "هر وقت آماده بودی، دکمه‌ی ادامه رو بزن.")
            return self._result(bot, fields, len(QUESTIONS),
                                needs_user=False, can_start=True,
                                summary=summary)

        if any(w in msg for w in EDIT_WORDS):
            bot = ("باشه، مشکلی نیست! کدوم بخش رو عوض کنیم؟ " +
                   "، ".join(f"«{q['short']}»" for q in QUESTIONS))
            fields["_editing"] = True
            self._save(state, fields, len(QUESTIONS))
            return self._result(bot, fields, len(QUESTIONS), summary=summary)

        if fields.get("_editing"):
            # Find which part they want to complete. The question is NOT
            # re-asked from scratch: their next message is simply appended
            # to the previous answer (handled above via _append_key).
            for q in QUESTIONS:
                if q["short"] in msg or q["key"] in msg.lower():
                    fields["_editing"] = False
                    fields["_append_key"] = q["key"]
                    self._save(state, fields, len(QUESTIONS))
                    return self._result(
                        f"باشه — چی می‌خوای به «{q['short']}» اضافه بشه؟ "
                        "همینو بنویس، به جواب قبلیت اضافه‌ش می‌کنم.",
                        fields, len(QUESTIONS), summary=summary)
            return self._result(
                "متوجه نشدم کدوم بخش — یکی از این‌ها رو بنویس: " +
                "، ".join(q["short"] for q in QUESTIONS),
                fields, len(QUESTIONS), summary=summary)

        return self._result(
            "برای ادامه فقط «تایید» یا «ویرایش» رو بنویس 🙂",
            fields, len(QUESTIONS), summary=summary)

    # ── LLM turn (structured) ──────────────────────────────────
    def _llm_turn(self, fields, qi, history,
                  already_probed: bool) -> Dict[str, Any]:
        q = QUESTIONS[qi]
        if self._client is None:
            # No key: accept any non-trivial answer, probe once for very
            # short ones.
            last = history[-1]["content"] if history else ""
            if len(last) < 12 and not already_probed:
                return {"reply": FALLBACK_PROBE,
                        "question_status": "needs_more"}
            return {"reply": "", "question_status": "collected",
                    "extracted_answer": last}

        collected_txt = "\n".join(
            f"- {x['short']}: {fields.get(x['key'])}"
            for x in QUESTIONS if fields.get(x["key"])) or "(هنوز هیچ)"

        probe_rule = (
            "You have ALREADY asked one follow-up for this question, so now "
            "you MUST return 'collected' and work with whatever they gave — "
            "do not ask for more."
            if already_probed else
            "If the answer is on-topic but thin/short/vague (e.g. one or two "
            "generic words, no concrete detail), return 'needs_more' and in "
            "'reply' ask ONE short, CONCRETE narrowing question about "
            f"'{q['key']}' ONLY, built from THEIR OWN words (e.g. goal "
            "'مهاجرت' → «مهاجرت برای چی؟ تحصیل، کار یا زندگی؟»; place 'در "
            "جلسه' → «جلسه کجاست؟ چه شکلیه؟»). NEVER ask them to 'describe "
            "the moment/scene' in general — the scene is covered by later "
            "questions, and vague invitations confuse people. Only one such "
            "follow-up is allowed."
        )

        # Which step comes after this one, so the LLM can phrase that question
        # itself instead of the backend appending a fixed string. The reference
        # wording is passed so nothing in the step (the 24-hour rule, the
        # examples) gets lost when it is rephrased.
        next_qi = next(
            (i for i, x in enumerate(QUESTIONS)
             if i != qi and not fields.get(x["key"])),
            None,
        )
        if next_qi is None:
            next_hint = ("(none — this is the last step; omit next_question)")
        else:
            nq = QUESTIONS[next_qi]
            next_hint = (f"key='{nq['key']}', role={nq.get('zoom', '')}\n"
                         f"reference wording: {nq['text']}")

        # STATIC FIRST, VARIABLE LAST — deliberately.
        #
        # This prompt goes out on every turn (~12 per participant) and used to
        # be ~2,200 tokens with the step details woven through it. Providers
        # cache identical prompt PREFIXES, so interleaving per-step variables
        # meant nothing could ever be reused and the full prompt was billed
        # every time. Everything constant now sits in one block that is
        # byte-identical across turns and participants, and the volatile state
        # comes after it.
        #
        # Keep it that way when editing: moving one f-string interpolation
        # upward silently un-caches every token above it.
        static_rules = """You are a warm, steady Persian-speaking guide helping
a person find ONE specific future day where they
have made progress toward their own long-term goal connected to the task
they chose. Do not assume that their task is English learning or academic research. An AI later turns their description into an IMAGE, so answers must
be concrete and visual.

WHO YOU ARE TALKING TO: people unsure about their future and often anxious
about it. Imagining a good future can feel naive or painful. Be a guide, not
an interviewer. Never imply there is a right answer.

EFT FUNDAMENTALS — use these to answer their questions for real:
- We build an EPISODE, not a prediction. It need not come true; a specific
  sensory scene can be re-visited mentally, which makes a distant goal feel
  closer and worth working for.
- Specific beats impressive. One ordinary day imagined vividly works better
  than a grand milestone imagined vaguely.
- Reaching their personal goal can be just ONE PART of that day's feeling.
- Present tense makes it feel like a memory of the future, not a plan.
- Being unsure about the future is normal and no obstacle to this.

ANSWER ANYTHING, STORE ONLY THE ACTIVE STEP:
- Discuss any doubt they raise — what this is for, whether it is silly, what
  if they never graduate, what if they cannot picture anything. Resolve it
  properly, THEN continue. Never defer with "we'll come back to that".
- Only the ACTIVE step is ever stored. Never record an off-topic turn as
  scene content, and never treat a question of theirs as an answer.
- If they don't know what to say: status='off_topic', give 1-2 tiny concrete
  examples for THIS step, invite their own version, and mention they can tap
  «الهام بگیر» for more — but the scene must end up theirs, not the example's.
- If they say they already answered, look back: if it is really there, return
  status='collected' with that earlier content; if not, re-ask gently.
- extracted_answer is ONLY real scene content in their own words — never a
  question, objection, or remark about the conversation. Never invent it.
- If they describe their PRESENT life instead of the future moment, warmly
  re-anchor with «وقتی به هدفت رسیدی» (never restate their goal text).
- FEELING step: collect POSITIVE emotions. If only negative ones come, accept
  kindly and ask once what good feeling sits alongside.

PRESENT TENSE: mirror their content back as happening now, even if they wrote future tense. Never correct them.

STEP DISCIPLINE:
- A specific place (room, building, floor, city, or address) fully answers WHERE.
  Accept it as collected; do not ask for objects, sounds, weather, people, or actions.
- Evaluate only the active field. Do not require information belonging to another step.
- Never invent sensory details, furniture, weather, actions, or people in reply or extraction.
- Reply is at most one short conversational acknowledgment, not a narrated scene.
- Use natural colloquial Persian: هستی، می‌کنی، می‌بینی. Avoid هستم، می‌آید، بنویسید.

TONE: Persian, warm, unhurried, never hyped. No «واااای»/«فوق‌العاده!». At
most one small emoji, often none. MAX 1-2 short sentences (up to 4 only when
resolving a real confusion). Normalize hesitation in passing. Never praise
them for answering, never make them feel tested. No body-related questions.
English answers are fine.

NEXT QUESTION IS YOURS TO PHRASE: when status='collected', also write
'next_question' — the next step's question in your own words, connected to
what they just said. Cover the same ground as the reference wording given
below, including its examples and constraints, without copying it verbatim.
Omit it if there is no next step.

Return STRICT JSON:
{"reply": "<short Persian reply>",
 "question_status": "off_topic" | "needs_more" | "collected",
 "extracted_answer": "<cleaned answer in their own words, or null>",
 "next_question": "<your phrasing of the next step, or null>"}"""

        system = f"""{static_rules}

── THIS TURN ──
Active step {qi + 1}/7: '{q['key']}' — {q.get('zoom', '')}
Reference wording: {question_text(qi, fields)}
{probe_rule}

Collected so far:
{collected_txt}

NEXT STEP TO ASK: {next_hint}"""

        try:
            # 6 messages, not 10: every earlier answer is already summarised
            # in `collected_txt` above, so a long tail of raw history repeats
            # the same content at full price. 6 keeps the immediate
            # back-and-forth (probe, off-topic exchange) that the model needs
            # to judge THIS turn.
            messages = [{"role": "system", "content": system}] + history[-6:]
            if CHAT_MODEL.startswith(("gpt-5", "o")):
                # GPT-5 family are reasoning models: no temperature control,
                # max_completion_tokens instead of max_tokens, and a
                # reasoning_effort knob (minimal = fast chat turns).
                res = self._client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages,
                    # Reasoning tokens are billed against this same budget, so
                    # it has to cover the thinking AND the JSON. Too low and
                    # the model spends it all reasoning and returns EMPTY
                    # content — which used to read as a valid empty decision.
                    max_completion_tokens=1500,
                    reasoning_effort="minimal",
                    response_format={"type": "json_object"},
                )
            else:
                res = self._client.chat.completions.create(
                    model=CHAT_MODEL,
                    messages=messages,
                    max_tokens=700,
                    # Low temperature: probe questions must be consistently
                    # concrete run-to-run, not creatively rephrased.
                    temperature=0.3,
                    response_format={"type": "json_object"},
                )
            content = (res.choices[0].message.content or "").strip()
            if not content:
                # A truncated or empty completion is a FAILURE, not an empty
                # answer. json.loads("{}") yields a dict, which used to fall
                # straight through as status='collected' with no reply — so
                # the participant's raw message was stored as scene content
                # and the step advanced, silently, logging a clean 200.
                finish = getattr(res.choices[0], "finish_reason", "?")
                usage = getattr(res, "usage", None)
                print(f"⚠️ chat LLM returned EMPTY content "
                      f"(finish_reason={finish}, usage={usage}) — treating as "
                      f"failure; raise max_completion_tokens if this repeats")
                return {"reply": "", "question_status": "llm_error"}
            out = json.loads(content)
            if isinstance(out, dict) and out:
                return out
            print(f"⚠️ chat LLM returned unusable JSON: {content[:200]!r}")
        except Exception as e:
            print(f"⚠️ chat LLM turn failed: {type(e).__name__}: {e}")
        # Failure → re-ask, do NOT store. The old behaviour returned
        # 'collected' with the raw message as the answer, so a transient API
        # error silently wrote whatever the participant happened to have typed
        # (often a question of their own) into the episode and advanced a step.
        # Staying put costs one turn; storing garbage corrupts the episode and
        # the image built from it.
        return {"reply": "", "question_status": "llm_error"}

    # ── inspire ────────────────────────────────────────────────
    def inspire(self) -> Dict[str, Any]:
        """Broad prompts for the ACTIVE step, to unstick a blank imagination.

        Fixed text, identical for everyone, no model call — see
        FALLBACK_INSPIRE for why they are deliberately broad rather than
        finished scenes.

        Nothing here is ever written into `fields`. They reach the UI as
        editable text the participant still has to make their own: an episode
        the participant did not actually imagine would be worthless as data,
        and the image is built from that episode.
        """
        state = self._get_or_create_state()
        qi = int(state.current_step)
        if qi >= len(QUESTIONS):
            return {"question_index": qi, "suggestions": []}
        return {
            "question_index": qi,
            "suggestions": list(FALLBACK_INSPIRE.get(QUESTIONS[qi]["key"], [])),
        }

    # ── final review ───────────────────────────────────────────
    def _bullet_text(self, fields) -> str:
        """The raw collected answers, one bullet per step."""
        parts = []
        for q in QUESTIONS:
            v = fields.get(q["key"])
            if v:
                parts.append(f"• {q['short']}: {v}")
        return "\n".join(parts)

    def _review_text(self, fields) -> str:
        """The episode as a first-person, PRESENT-TENSE paragraph.

        Present tense is the point, not decoration: narrating the scene as
        happening now («دارم قهوه سفارش می‌دم») rather than as something that
        will happen is what lets the participant subjectively pre-experience
        it, which is the mechanism the whole intervention rests on. Most
        people naturally write in future tense, so the rewrite closes that gap.

        The participant is shown this text and confirms it before anything is
        locked, so nothing is put in their mouth silently — and the raw
        per-step answers stay untouched in `fields` for analysis.

        Falls back to the bullet list whenever the LLM is unavailable or
        returns something unusable: a plain listing of their own words is
        always a safe thing to show.
        """
        bullets = self._bullet_text(fields)
        if not bullets or self._client is None:
            return bullets

        scene = "\n".join(
            f"{q['short']}: {fields.get(q['key'])}"
            for q in QUESTIONS if fields.get(q["key"])
        )
        system = (
            "Rewrite the participant's answers as ONE short Persian paragraph "
            "describing their future day, in FIRST PERSON and PRESENT TENSE "
            "(«دارم...»، «هستم»، «حس می‌کنم») — never future tense «خواهم».\n"
            "Rules:\n"
            "- Use ONLY what they actually said. Add no new detail, place, "
            "person, object or emotion. Invent nothing.\n"
            "- Keep their own words and register wherever possible; you are "
            "changing tense and stitching sentences, not improving their "
            "writing.\n"
            "- 2-4 short sentences, warm and plain. No preamble, no heading, "
            "no quotation marks — return the paragraph only.\n"
        )
        try:
            kwargs: Dict[str, Any] = {
                "model": CHAT_MODEL,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": scene},
                ],
            }
            if CHAT_MODEL.startswith(("gpt-5", "o")):
                kwargs["max_completion_tokens"] = 500
                kwargs["reasoning_effort"] = "minimal"
            else:
                kwargs["max_tokens"] = 300
                # Low temperature: this is a faithful tense conversion, not a
                # creative rewrite.
                kwargs["temperature"] = 0.2
            res = self._client.chat.completions.create(**kwargs)
            out = (res.choices[0].message.content or "").strip()
            if out:
                return out
        except Exception as e:
            print(f"⚠️ present-tense summary rewrite failed: {e}")
        return bullets
