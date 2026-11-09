

from __future__ import annotations
from datetime import datetime
from typing import Optional, Literal
import uuid
from pydantic import EmailStr

from sqlalchemy import (
    String, Integer, Float, DateTime, func, false, ForeignKey, Text, JSON,
    Enum, Index, Column, UniqueConstraint, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db_setup import Base
# ─────────────────────────────
# USER

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True
    )
    # Anonymous auth: system-generated participant code + simple password.
    participant_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name_fa: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # BETWEEN-SUBJECTS ARM, fixed at signup and never changed afterwards.
    #   "eft"     – guided EFT chat + their own personalized reminder image
    #   "control" – no chat, no personal image; the shared generic reminders
    # Assigned once and stored, rather than derived later, because a
    # participant's whole route through the study depends on it: re-deriving
    # it anywhere risks a person seeing one arm and being analysed as the
    # other. Nullable only so databases created before this column can be
    # migrated in place.
    study_group: Mapped[Optional[str]] = mapped_column(
        String(16), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    degree: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    examGoal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    studyHoursPerWeek: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    __table_args__ = (
        UniqueConstraint("participant_code", name="uq_users_participant_code"),
    )

    # Relations
    eft_response: Mapped[Optional["EFTResponse"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    ai_prompts: Mapped[list["AIPrompt"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    nudges: Mapped[list["Nudge"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    activities: Mapped[list["UserActivity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    stats: Mapped["UserStats"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # Baseline/demographic profile (one-to-one)
    participant_profile: Mapped[Optional["ParticipantProfile"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    # Structured EFT episodes (one-to-many)
    eft_episodes: Mapped[list["EFTEpisode"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    # Study feedback records (one-to-many)
    study_feedback: Mapped[list["StudyFeedback"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


    

    # Current EFT chat state (one-to-one transient state)
    eft_chat_state: Mapped[Optional["EFTChatState"]] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
def __repr__(self):
        return f"<User {self.participant_code!r} name={self.full_name_fa!r}>"


# ─────────────────────────────
# EFT RESPONSE (Persian form)
# ─────────────────────────────
class EFTResponse(Base):
    __tablename__ = "eft_responses"
    __table_args__ = (Index("ix_eft_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    timeFrame: Mapped[Optional[str]] = mapped_column(String(255))
    place: Mapped[Optional[str]] = mapped_column(String(255))
    activities: Mapped[Optional[str]] = mapped_column(String(255))
    people: Mapped[Optional[str]] = mapped_column(String(255))
    feelings: Mapped[Optional[str]] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


    user: Mapped["User"] = relationship(back_populates="eft_response")

    def __repr__(self):
        return f"<EFTResponse user_id={self.user_id}>"


# ─────────────────────────────
# AI PROMPTS (Prompt storage for reproducibility)
# ─────────────────────────────
class AIPrompt(Base):
    """
    Stores the actual text prompts used to generate nudges for a user.
    Keeping them allows analysis and reproducibility of AI behavior.
    """
    __tablename__ = "ai_prompts"
    __table_args__ = (Index("ix_prompt_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="gpt-4o-mini")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[str] = mapped_column(String(64), default="nudge_generation")  # or 'goal_summary', etc.
    response_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


    user: Mapped["User"] = relationship(back_populates="ai_prompts")

    def __repr__(self):
        return f"<AIPrompt id={self.id} user_id={self.user_id} purpose={self.purpose}>"


# ─────────────────────────────
# NUDGES
# ─────────────────────────────
NudgeType = Literal["positive", "negative"]
NudgeSource = Literal["ai", "manual"]

class Nudge(Base):
    __tablename__ = "nudges"
    __table_args__ = (Index("ix_nudge_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    nudge_number: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[str] = mapped_column(Enum("positive", "negative", name="nudge_type"), nullable=False)
    source: Mapped[str] = mapped_column(Enum("ai", "manual", name="nudge_source"), default="ai")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    related_prompt_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("ai_prompts.id", ondelete="SET NULL"), nullable=True
    )
    context: Mapped[Optional[dict]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


    user: Mapped["User"] = relationship(back_populates="nudges")
    prompt: Mapped[Optional["AIPrompt"]] = relationship()

    def __repr__(self):
        return f"<Nudge {self.type} user_id={self.user_id}>"


# ─────────────────────────────
# USER ACTIVITY (UK - activity/performance tracking)
# ─────────────────────────────
class UserActivity(Base):
    """
    Tracks all granular user events (reading, idle, focus, nudge, etc.)
    Useful for fine-grained behavioral timelines.
    """
    __tablename__ = "user_activity"
    __table_args__ = (Index("ix_activity_user_created", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    activity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    performance_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())


    user: Mapped["User"] = relationship(back_populates="activities")

    def __repr__(self):
        return f"<UserActivity user_id={self.user_id} type={self.activity_type}>"




# ─────────────────────────────
# EVENT LOG
# ─────────────────────────────
class EventLog(Base):
    """
    Stores raw frontend/backend system events.
    More generic than UserActivity — includes internal triggers and feedback events.
    """
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    details: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())
    user: Mapped["User"] = relationship(back_populates="event_logs")

    def __repr__(self):
        return f"<EventLog user_id={self.user_id} type={self.event_type}>"

# Add reverse relationship to User
User.event_logs = relationship("EventLog", back_populates="user", cascade="all, delete-orphan")


# ─────────────────────────────
# USER STATS (AGGREGATED METRICS)
# ─────────────────────────────

class UserStats(Base):
    __tablename__ = "user_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # eft feedback
    ratingVividness: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ratingSpecificity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ratingDifficulty: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ratingGoalImportance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    total_idle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_distraction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sustained_attention: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_refocus_within_60s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_nudges_shown: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_feedback_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="stats")


class Session(Base):
    """
    One focused work / study session for a user.
    Stores per-session metrics; UserStats will aggregate from here.
    """
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )

    session_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # timestamps
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # When the READING WINDOW itself began — distinct from started_at, which
    # is stamped when the session row is created (before the breathing
    # countdown). Cue slots are measured from this, so it is the server's
    # authoritative clock for the whole protocol. Nullable: a session exists
    # before its reading window opens.
    reading_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # per-session stats (same “shape” as UserStats but per session)
    idle_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    distraction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sustained_attention: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    refocus_within_60s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nudges_shown: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # feedback for each couple of sessions
    feedback_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    feedback_comment = mapped_column(Text, nullable=False, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="sessions")

# ─────────────────────────────
# PARTICIPANT PROFILE
# ─────────────────────────────
class ParticipantProfile(Base):
    """
    Stores baseline demographic and study context information for a user.
    Each user may have at most one profile; on subsequent submissions the
    existing record is updated.
    """
    __tablename__ = "participant_profiles"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    education_level: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    study_field: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    english_goal: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    english_level: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    study_frequency: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    english_importance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # Relationship back to user (optional)
    user: Mapped["User"] = relationship(back_populates="participant_profile")

# ─────────────────────────────
# EFT EPISODE
# ─────────────────────────────
class EFTEpisode(Base):
    """
    Stores a single episodic future thinking (EFT) episode constructed by
    the participant. The episode_json field contains all structured
    details (date, place, actions, people, sensory, emotion/body, identity,
    summary and confirmation) in JSON string form.
    Multiple episodes per user are allowed (e.g. across studies).
    """
    __tablename__ = "eft_episodes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    episode_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship(back_populates="eft_episodes")


# ─────────────────────────────
# EFT CHAT STATE (runtime only)
# ─────────────────────────────
class EFTChatState(Base):
    """
    Stores the transient state of an EFT chat conversation for a user.
    This is NOT research data; it only maintains continuity between turns.
    """
    __tablename__ = "eft_chat_states"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    fields_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship(back_populates="eft_chat_state")
# ─────────────────────────────
# STUDY FEEDBACK
# ─────────────────────────────

class StudyFeedback(Base):
    """
    Stores the participant's feedback after each study session, capturing
    self-reported vividness, accessibility, future-self connection, focus,
    effort and whether the episode came to mind, along with optional
    qualitative comments.
    """
    __tablename__ = "study_feedback"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_number: Mapped[int] = mapped_column(Integer, nullable=False)
    vividness: Mapped[int] = mapped_column(Integer, nullable=True)
    accessibility: Mapped[int] = mapped_column(Integer, nullable=True)
    future_self_connection: Mapped[int] = mapped_column(Integer, nullable=True)
    task_focus: Mapped[int] = mapped_column(Integer, nullable=True)
    effort: Mapped[int] = mapped_column(Integer, nullable=True)
    episode_recall: Mapped[Optional[bool]] = mapped_column(Integer, nullable=True)  # store as 0/1
    recall_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    help_comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    user: Mapped["User"] = relationship(back_populates="study_feedback")

# ─────────────────────────────
# EXTENSION REMINDER IMAGE
# ─────────────────────────────
class ExtensionReminder(Base):
    """
    One active extension reminder image per user.
    For now this stores a test image URL.
    Later this will store the AI-generated cloud image URL.
    """
    __tablename__ = "extension_reminders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    cue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship()


# ─────────────────────────────
# REMINDER ASSETS (step 10: 3 generated images + cues per participant)
# ─────────────────────────────
class ReminderAsset(Base):
    """
    One generated reminder (image + text cue) for a participant. Each
    participant gets several (default 3) so the reminders don't repeat.
    The extension and the in-app overlay rotate through them.
    """
    __tablename__ = "reminder_assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    asset_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    cue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # True for the shared generic/motivational reminder used as the control
    # condition; False for the participant's own episode. Stored per asset so
    # an export can tell the two apart without re-deriving it from the URL.
    is_generic: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    user: Mapped["User"] = relationship()


# ─────────────────────────────
# RESEARCH EVENTS (step 11: one row PER TRIGGER, not per user)
# ─────────────────────────────
class ResearchEvent(Base):
    """FROZEN — the reactive protocol's event table. Read, never written.

    One row per disengagement trigger, from the design where a reminder fired
    *because* the participant disengaged. That conflated two things which are
    now separate: CueDelivery holds reminders (fixed schedule), and
    DisengagementEpisode holds disengagements (the outcome).

    Kept, and still exported, because these rows are the record of what the
    pilot actually did. They must NEVER be pooled with the new tables — they
    come from a different protocol and a different causal structure, and the
    latency column in particular means something else here (time to return
    after a reactive cue, which cannot be compared with a scheduled one).
    """
    __tablename__ = "research_events"

    # event_id
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # participant_id: internal numeric user id (anonymous)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # tab_switch | idle
    event_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now(), nullable=False
    )

    # personalized | neutral (percentage configurable; 100% personalized now)
    condition_assigned: Mapped[str] = mapped_column(
        String(20), nullable=False, default="personalized"
    )

    reminder_shown_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    returned_to_reading: Mapped[bool] = mapped_column(
        Integer, nullable=False, default=0
    )  # stored 0/1
    return_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    return_latency_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    clicked_return: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)
    dismissed: Mapped[bool] = mapped_column(Integer, nullable=False, default=0)

    reading_time_after_return: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )  # seconds until next trigger / session end
    repeated_disengagement_after_return: Mapped[Optional[bool]] = mapped_column(
        Integer, nullable=True
    )

    user: Mapped["User"] = relationship()




# ─────────────────────────────
# SCHEDULED CUES  (one row per slot)
# ─────────────────────────────
class CueDelivery(Base):
    """One scheduled reminder slot.

    Replaces the trigger-shaped ResearchEvent for cue data. Those two used to
    be the same row because a reminder only ever existed as a reaction to a
    disengagement; on a fixed clock they are different things, and conflating
    them makes both unanalysable.

    Rows are created UP FRONT, when the reading window opens, rather than at
    delivery. That way a cue that never reached the participant is a visible
    NULL with a reason attached, instead of an absent row — the difference
    between "no cue was needed" and "delivery failed", which the old schema
    could not express.
    """
    __tablename__ = "cue_deliveries"
    __table_args__ = (
        # The app and the extension both race to deliver a due slot. They are
        # near-exclusive in practice (the study tab is either in front or it
        # is not), but "near" is not a guarantee, and a double-delivered slot
        # would break the equal-dosage claim the whole design rests on.
        UniqueConstraint("session_id", "slot", name="uq_cue_session_slot"),
        Index("ix_cue_participant", "participant_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[int] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # 1 = minute 10, 2 = minute 20. Kept as a fixed effect in analysis so any
    # order or fatigue difference between the two is absorbed rather than
    # attributed to the intervention.
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    # ── delivery ──
    claimed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    claimed_by: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # How late the cue actually was, in ms. chrome.alarms has a 30s floor and
    # a suspended service worker can add more, so timing precision is AUDITED
    # rather than assumed: "minute 10" is a claim this column can check.
    delivery_offset_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    # active | idle | off_tab | off_browser — the attentional state at the
    # moment the slot opened. This is what splits the two primary measures:
    # return latency is only defined for the off-tab states, retention only
    # for `active`. They answer different questions and must never be pooled.
    state_at_delivery: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True
    )
    # corner_card | in_app_overlay | full_page_modal
    form: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)

    # personalized | neutral — set server-side from the participant's arm,
    # never from what the client reports it rendered.
    condition: Mapped[str] = mapped_column(
        String(20), nullable=False, default="personalized"
    )
    asset_image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    asset_cue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── outcomes ──
    dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    clicked_return: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    # PRIMARY MEASURE 1 — only for cues delivered off-tab. Milliseconds
    # because the blueprint specifies ms and whole seconds throw away most of
    # the resolution in a measure whose interesting range is a few seconds.
    return_latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    # PRIMARY MEASURE 2 — only for cues delivered while active: seconds from
    # the cue until the next disengagement begins.
    post_cue_focus_seconds: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True
    )

    # Why a slot produced no delivery. Never left as a bare NULL delivery.
    not_delivered_reason: Mapped[Optional[str]] = mapped_column(
        String(40), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    user: Mapped["User"] = relationship()

    def __repr__(self):
        return (f"<CueDelivery p={self.participant_id} slot={self.slot} "
                f"state={self.state_at_delivery}>")


# ─────────────────────────────
# DISENGAGEMENT EPISODES
# ─────────────────────────────
class DisengagementEpisode(Base):
    """One episode of the participant not reading — a tab switch or idle.

    Independent of any cue. That independence IS the design change: under the
    reactive protocol a disengagement only got recorded because it triggered
    a reminder, so disengagement was the trigger. Here it is the outcome, and
    it is counted whether or not a cue was anywhere near it.
    """
    __tablename__ = "disengagement_episodes"
    __table_args__ = (
        Index("ix_diseng_participant_started", "participant_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    episode_type: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    ended_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # return | session_end | abandoned. An episode still open when the window
    # closes is not the same as one the participant came back from, and
    # time-on-task is wrong if the two are treated alike.
    ended_by: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Denormalised on purpose: this is the join key for the retention measure,
    # and computing it at write time avoids rebuilding each participant's
    # timeline across two tables during analysis.
    ms_since_last_cue: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    preceded_by_cue_slot: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    user: Mapped["User"] = relationship()

    def __repr__(self):
        return (f"<DisengagementEpisode p={self.participant_id} "
                f"{self.episode_type} {self.duration_ms}ms>")


# ─────────────────────────────
# MEASUREMENT BATTERY
# ─────────────────────────────
class MeasureResponse(Base):
    """One answered item from the measurement battery.

    One ROW PER ITEM rather than a column per item, because the battery is
    still being settled: adding or dropping an item must not require a schema
    change on a live study database. It also makes the export long-format,
    which is what an analysis actually wants.

    (user_id, item_code, timepoint) is unique so a participant who resubmits a
    page updates their answers instead of silently producing two conflicting
    rows for the same question.

    `timepoint` is the whole point of the table: fsc and intention are asked at
    baseline AND closing, and the analysis is the CHANGE between them. Without
    the timepoint the two are indistinguishable.
    """
    __tablename__ = "measure_responses"
    __table_args__ = (
        UniqueConstraint("user_id", "item_code", "timepoint",
                         name="uq_measure_user_item_timepoint"),
        Index("ix_measure_user_timepoint", "user_id", "timepoint"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 'goal_importance' | 'asayama_eft' | 'tipi' | 'sus' |
    # 'reminder_experience' | 'attention_check'
    instrument: Mapped[str] = mapped_column(String(32), nullable=False)
    item_code: Mapped[str] = mapped_column(String(48), nullable=False)
    # 'baseline' | 'post_chat' | 'onboarding_inventory' | 'post_task' |
    # 'closing'
    timepoint: Mapped[str] = mapped_column(String(24), nullable=False, index=True)
    # Study phase 1-6, carried so an export can be ordered by protocol stage
    # without re-deriving it from the timepoint name.
    phase: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    text_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Stored per response rather than looked up at analysis time: the item
    # bank can change, and a row must stay interpretable on its own.
    reverse: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    scale_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    scale_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # TRUE  = a published, validated instrument used verbatim (translated).
    # FALSE = a study-specific HCI evaluation item, written for this study,
    #         which must NEVER be reported as a validated psychological scale.
    #
    # Stamped onto the ROW, not looked up at analysis time. The item bank is
    # edited during piloting, and the one thing that must not drift is which
    # category an already-collected answer belonged to — that is the
    # distinction the whole write-up rests on.
    validated: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # The precise provenance category — published_original /
    # published_translated / published_adapted / study_specific_hci /
    # study_specific_open_ended / deprecated. The boolean above cannot
    # express the difference between "published but translated" and
    # "published but reworded", and that difference decides how an item may
    # be described in a write-up.
    measure_status: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True
    )
    # Which battery version produced this answer. Stamped per row so an
    # export can never silently pool two protocol versions.
    battery_version: Mapped[Optional[str]] = mapped_column(
        String(48), nullable=True
    )
    # Duration items (intended study time) only. The raw entry is kept
    # ALONGSIDE the normalised total in `value`, because "2h 30m" and "150
    # minutes" are the same quantity but not the same answer, and only the
    # raw pair shows how the participant actually thought about it.
    entered_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    entered_minutes: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True
    )
    # Full citation for a published item; "Study-specific HCI evaluation
    # item" otherwise. Denormalised for the same reason as `validated`.
    source: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=func.now()
    )

    user: Mapped["User"] = relationship()
