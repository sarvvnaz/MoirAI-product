"""Personalized reminder generation (image + text cue).

Turns the participant's confirmed EFT episode into:
  - an AI-generated image saved under app/static/reminders/
  - a short future-oriented Persian text cue

Reliability first: every step has a fallback so the study never blocks on
OpenAI. If image generation fails, the previous/placeholder image URL is kept.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

from sqlalchemy.orm import Session

from app.config import (
    BUNDLED_STATIC_DIR,
    IMAGE_MODEL,
    PROMPT_MODEL,
    REMINDERS_DIR,
    image_client,
    openai_client,
)
from app.database import models


# Read-only assets (the placeholder image) ship with the code; generated
# images go to REMINDERS_DIR, which points at the persistent disk in
# deployment. Both are re-exported here so existing call sites keep working.
STATIC_DIR = BUNDLED_STATIC_DIR

FALLBACK_CUE = "همان لحظه‌ای که برایش تلاش می‌کنم — دارم می‌بینمش."

# Enforced on EVERY generated image prompt (appended server-side so the
# per-scene prompt can never override the study's visual requirements:
# realistic, face never visible, setting + feeling emphasized, no text,
# and — importantly — anatomically clean, no close-ups of hands, since
# generators produce disturbing extra-fingers/extra-hands artifacts there).
IMAGE_STYLE_SUFFIX = (
    ". Photorealistic photograph, warm natural light, calm cinematic "
    "composition, shallow depth of field. FIRST-PERSON POINT OF VIEW: the "
    "camera is the learner's own eyes, so we see the moment exactly as they "
    "see it — the room, the people facing them, the desk in front of them. "
    "Because it is their own viewpoint, the learner themself is simply not "
    "in the frame; this must look like a natural photograph taken from where "
    "they stand, never like a portrait with a hidden or cropped face. Other "
    "people must have no recognizable or detailed faces: use natural neck-down framing "
    "or gentle photographic depth-of-field blur across their faces. Prefer naturally "
    "composed waist-up bodies cropped below the chin, or distant softly defocused people. "
    "Never blank, erase, mask, pixelate, deform, or obscure faces with objects; no "
    "headless-looking bodies, uncanny faceless skin, or unsettling silhouettes. "
    "Do NOT make hands the subject and do NOT show close-ups of hands or "
    "fingers; if any of the learner's own hands appear at the frame edge "
    "keep them small, natural and incidental, with correct human anatomy "
    "(no extra limbs or fingers). Emphasize the SETTING and the calm, "
    "hopeful FEELING of the moment. No readable text, letters, numbers, "
    "logos or signs anywhere in the image."
)

# Episode field keys (the 7 EFT questions, work-step-12 format — must match
# eft_chat_service_v2.QUESTIONS order).
_EPISODE_KEYS = [
    "goal",     # 1. the academic goal (defence, graduation, publication)
    "where",    # 2. where they are in that future moment
    "when",     # 3. when it happens
    "action",   # 4. what exactly they are doing
    "objects",  # 5. objects/details around them
    "who",      # 6. alone, or who is with them
    "feeling",  # 7. how they feel in that moment
]


# Client factory lives in app/config.py so base_url + key are applied
# identically everywhere (see openai_client).
_client = openai_client
_image_client = image_client


def _prompt_completion(client, prompt: str, max_tokens: int,
                       temperature: float = 0.9) -> str:
    """A text completion from PROMPT_MODEL, whatever family it belongs to.

    The GPT-5 family rejects `temperature` and needs `max_completion_tokens`
    instead of `max_tokens`; it also spends that budget on reasoning first, so
    too small a cap returns EMPTY content rather than an error. Both mistakes
    were live here: every call passed max_tokens+temperature, so with
    PROMPT_MODEL=gpt-5-mini the episode-to-image-prompt step came back empty
    and json.loads("") failed with "Expecting value: line 1 column 1".

    The visible effect was not an error but a wrong picture: the caller fell
    back to a generic hardcoded prompt, so participants got a stock scene and
    FALLBACK_CUE instead of anything from their own episode.

    Returns "" when the model gives nothing usable — callers already treat
    that as failure.
    """
    kwargs: dict = {"model": PROMPT_MODEL,
                    "messages": [{"role": "user", "content": prompt}]}
    if PROMPT_MODEL.startswith(("gpt-5", "o")):
        # Headroom over the caller's figure: the reasoning tokens come out of
        # the same allowance and would otherwise leave nothing for the answer.
        kwargs["max_completion_tokens"] = max(max_tokens * 2, 1200)
        kwargs["reasoning_effort"] = "minimal"
    else:
        kwargs["max_tokens"] = max_tokens
        kwargs["temperature"] = temperature

    res = client.chat.completions.create(**kwargs)
    out = (res.choices[0].message.content or "").strip()
    if not out:
        finish = getattr(res.choices[0], "finish_reason", "?")
        print(f"⚠️ {PROMPT_MODEL} returned EMPTY content "
              f"(finish_reason={finish}, usage={getattr(res, 'usage', None)})")
    return out


def _image_bytes_from_response(res) -> bytes | None:
    """Return generated image bytes from either base64 or URL responses."""
    if not getattr(res, "data", None):
        return None

    item = res.data[0]
    b64 = getattr(item, "b64_json", None)
    if b64:
        return base64.b64decode(b64)

    image_url = getattr(item, "url", None)
    if image_url:
        return _download_image(image_url)

    return None


def _download_image(image_url: str) -> bytes | None:
    """Fetch a generated image from a URL the provider returned.

    Measured reality on the deployed server: this does not work with AvalAI.
    It answers with a Cloudflare Worker URL (image-proxy-worker.*.workers.dev)
    and that host is unreachable from Iranian networks — /api/research/netcheck
    showed IPv4 timing out AND IPv6 failing to bind, i.e. the host is blocked,
    not mis-routed. An earlier attempt to force IPv4 made it worse, failing
    with "[Errno -9] Address family for hostname not supported".

    So there is no client-side fix. The image is generated, billed, and then
    unreachable. Kept because OpenAI-direct and other gateways do return
    fetchable URLs, but on AvalAI expect this to fail and the generic
    reminder to be used instead.
    """
    try:
        request = Request(image_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=60) as response:
            return response.read()
    except Exception as e:
        print(f"⚠️ image WAS generated but could not be downloaded from "
              f"{image_url[:70]}…: {type(e).__name__}: {e}\n"
              f"   If this is AvalAI: their image URLs are on a host blocked "
              f"from Iran. Ask them to return base64 (response_format / "
              f"b64_json) — no change on this side can reach that URL.")
        return None


def _generate_image_bytes(img, prompt: str) -> bytes | None:
    """images.generate, returning the image bytes whichever way they arrive.

    response_format is deliberately NOT sent. Measured against both providers:
    OpenAI's gpt-image-1 returns b64 natively and rejects the parameter, and
    the AvalAI gateway ignores it and answers with a URL regardless — but
    rather than a clean 400 it hung for 152s before erroring, which would
    double the wait on every single image for no benefit.

    So: ask plainly, take b64 when it comes, and download the URL over IPv4
    when it does not.
    """
    res = img.images.generate(
        model=IMAGE_MODEL, prompt=prompt,
        size="1024x1024", quality="medium", n=1,
    )
    return _image_bytes_from_response(res)


def _latest_episode_fields(db: Session, user_id: int) -> dict:
    episode = (
        db.query(models.EFTEpisode)
        .filter(models.EFTEpisode.user_id == user_id)
        .order_by(models.EFTEpisode.created_at.desc())
        .first()
    )
    if episode is None:
        return {}
    try:
        return json.loads(episode.episode_json)
    except Exception:
        return {}


def _episode_text(fields: dict) -> str:
    parts = []
    for key in _EPISODE_KEYS:
        value = fields.get(key)
        if value:
            parts.append(f"{key}: {value}")
    summary = fields.get("_summary")
    if summary:
        parts.append(f"summary: {summary}")
    return "\n".join(parts)


def _log_prompt(db: Session, user_id: int, purpose: str,
                prompt_text: str, response_preview: str) -> None:
    try:
        db.add(models.AIPrompt(
            user_id=user_id,
            model_name="gpt-4o-mini/gpt-image-1",
            prompt_text=prompt_text,
            purpose=purpose,
            response_preview=response_preview[:500],
        ))
    except Exception as e:
        print(f"⚠️ Could not log AI prompt: {e}")


def generate_cue(db: Session, user_id: int, fields: dict) -> str:
    """One short future-oriented Persian sentence tied to the episode."""
    summary = (fields.get("_summary") or "").strip()
    client = _client()
    episode_text = _episode_text(fields)

    if client is not None and episode_text:
        prompt = (
            "بر اساس این اپیزود آینده‌نگری کاربر، فقط «یک» جمله‌ی کوتاه فارسی "
            "(حداکثر ۲۰ کلمه) بنویس که مثل یک یادآور گرم و شخصی، لحظه‌ی آینده‌ی "
            "او را زنده کند.\n"
            "جمله باید «اول‌شخص» و از زبان خودِ کاربر باشد (من/دارم/می‌بینم…) — "
            "انگار فکر خودش است؛ هرگز او را با «تو» خطاب نکن. "
            "اول حس، بعد موقعیت. بدون نصیحت، بدون گیومه، فقط همان یک جمله.\n\n"
            f"{episode_text}"
        )
        try:
            cue = _prompt_completion(client, prompt, 80).strip('"«»')
            if cue:
                _log_prompt(db, user_id, "reminder_cue", prompt, cue)
                return cue
        except Exception as e:
            print(f"⚠️ Cue generation failed: {e}")

    if summary:
        return summary[:180]
    return FALLBACK_CUE


def _gender_rule(raw_gender: str | None) -> str:
    """English prompt fragment describing the learner's gender.

    Only applied when the participant explicitly chose زن/مرد in the baseline
    profile — otherwise the figure stays ambiguous. Faces are never visible,
    so HAIR is the visual gender cue: short brown hair for men, long/medium
    brown hair (wavy or straight) for women.
    """
    gender = (raw_gender or "").strip()
    if gender == "زن":
        return ("The learner is a WOMAN: whenever the figure appears, give "
                "her long or medium-length brown hair (wavy or straight) so "
                "she reads clearly as a woman even from behind — still shown "
                "from behind / over-the-shoulder, never identifiable. ")
    if gender == "مرد":
        return ("The learner is a MAN: whenever the figure appears and hair "
                "is visible, give him short brown hair so he reads clearly "
                "as a man even from behind — still shown from behind / "
                "over-the-shoulder, never identifiable. ")
    return ("Do NOT specify or imply the learner's gender; "
            "keep the figure ambiguous and dont show their face (from behind, distant, "
            "or setting-only). ")


def _build_image_prompt(db: Session, user_id: int, fields: dict) -> str:
    episode_text = _episode_text(fields)
    fallback_prompt = (
        "A warm, hopeful digital illustration of a young student achieving "
        "their academic goal in the near future, soft light, "
        "optimistic mood, no text, no words in the image and no faces naturally visible."
    )
    client = _client()
    if client is None or not episode_text:
        return fallback_prompt

    user = db.query(models.User).filter(models.User.id == user_id).first()
    prompt = (
        "Write a single vivid English prompt (max 70 words) for an image "
        "generation model. The image must depict this person's imagined "
        "positive future moment in FIRST-PERSON point of view — the camera is "
        "their own eyes, so they are naturally out of frame (never their face, "
        "never their back, never a cropped face). Warm optimistic photographic "
        "style, soft lighting. Strictly no text, letters or words in the "
        "image. "
        + _gender_rule(user.gender if user else None) +
        "Base it faithfully on this episode (written in Persian):\n\n"
        f"{episode_text}"
    )
    try:
        image_prompt = _prompt_completion(client, prompt, 140, temperature=0.8)
        if image_prompt:
            _log_prompt(db, user_id, "reminder_image_prompt", prompt, image_prompt)
            return image_prompt
    except Exception as e:
        print(f"⚠️ Image prompt generation failed: {e}")
    return fallback_prompt


def generate_image(db: Session, user_id: int, fields: dict) -> str | None:
    """Generates the reminder image and returns its /static/... URL path.

    Returns None on any failure (caller keeps the previous image URL).
    """
    # Image client, not the chat one: chat calls are capped at a few seconds
    # so a dead provider fails while the participant is still waiting, but
    # image generation legitimately runs for minutes and that cap would abort
    # every single one.
    client = _image_client()
    if client is None:
        return None

    image_prompt = _build_image_prompt(db, user_id, fields)
    try:
        res = client.images.generate(
            model=IMAGE_MODEL,
            prompt=image_prompt,
            size="1024x1024",
            quality="medium",
            n=1,
        )
        image_bytes = _image_bytes_from_response(res)
        if not image_bytes:
            return None
        REMINDERS_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"user_{user_id}.png"
        (REMINDERS_DIR / filename).write_bytes(image_bytes)
        _log_prompt(db, user_id, "reminder_image", image_prompt, filename)
        # Cache-busting version so the extension refetches after regeneration.
        return f"/static/reminders/{filename}?v={int(time.time())}"
    except Exception as e:
        print(f"⚠️ Image generation failed: {e}")
        return None


# Few-shot guidance for the reminder-set meta-prompt (condensed from the
# research team's examples: 7 EFT answers → image description → short cue).
#
# The two examples are ACADEMIC on purpose. The old ones were English-class
# scenes, and a few-shot set that models a different domain teaches the
# generator to reach for that domain's imagery regardless of what the
# participant actually described — the participant's own episode was losing
# to the example's.
_FEW_SHOT = """
EXAMPLE A (episode: goal=defend my thesis; situation=presenting my results
to the committee; when=one year from now; where=university defence hall,
round table, projector; who=supervisor and ~4 examiners; saying="my results
support the hypothesis I set out at the start."; feeling=a little nervous,
but proud and relieved)
→ image_prompt: "First-person view from a seat at a round table in a
university defence hall: a warm seminar room seen through the student's own
eyes, a printed copy of the thesis and a notebook on the table in front, a
projector screen glowing ahead, about four examiners and the supervisor across
the table looking towards the viewer and listening. Academic, focused,
slightly tense but hopeful atmosphere."
→ cue: "کمی مضطربم اما سربلند، دارم نتیجه‌های پژوهشم رو به داوران ارائه می‌دم."

EXAMPLE B (episode: goal=graduate with my degree; situation=receiving my
diploma at the graduation ceremony; where=university auditorium, stage,
curtains; who=family and friends in the audience; feeling=calm, proud, light)
→ image_prompt: "First-person view from the stage of a university auditorium
at a graduation ceremony: a warm hall seen through the student's own eyes, a
rolled diploma cover held just in front of them, rows of seats and blurred
figures of family and friends in the background, soft daylight from high
windows. Seen exactly as the student sees it, proud, celebratory and calm."
→ cue: "آرام و مطمئنم، مدرک فارغ‌التحصیلی رو توی دستم گرفتم."
"""


def generate_reminder_set(db: Session, user: models.User,
                          count: int = 1) -> list[models.ReminderAsset]:
    """Step 10: generates `count` distinct reminder images + cues from the
    participant's EFT episode (7-question format) and stores them as
    ReminderAsset rows.

    Image goals: photorealistic, faithful to the episode's SETTING and
    FEELING, the learner's face never visible (from behind / shoulders-down /
    hands only, or the setting alone), no readable text in the image.
    Cue goals: one short Persian sentence, FEELING first, then the situation
    (e.g. " سربلند در کلاس دانشگاه، ...").

    Falls back gracefully: any image that fails is skipped; if all fail the
    existing reminder (placeholder) stays in place.
    """
    fields = _latest_episode_fields(db, user.id)
    episode_text = _episode_text(fields)
    client = _client()

    # Every branch below can yield zero images, and most of them used to do it
    # without saying anything — the participant just got the generic fallback
    # while the log showed a clean 200. State the inputs up front so the cause
    # is visible from the logs alone.
    print(f"🖼️ reminder-set user={user.id} count={count} "
          f"episode_fields={len(fields or {})} "
          f"episode_text={len(episode_text or '')} chars "
          f"client={'ok' if client else 'NONE (no API key)'}")
    if client is None:
        print("🖼️ ABORT: no LLM client — check the key for the active provider")
    elif not episode_text:
        print("🖼️ ABORT: episode text is empty — the confirmed EFT episode "
              "is missing or has no usable fields")

    # 1) One LLM call → `count` distinct {image_prompt, cue} pairs.
    pairs: list[dict] = []
    if client is not None and episode_text:
        angle_rule = (
            "Each variation is the SAME episode seen through the learner's "
            "own eyes, but looking in a DIFFERENT direction: 1) straight "
            "ahead at the people or screen they are addressing, 2) down and "
            "across their own desk/table and what is on it, 3) a wider sweep "
            "of the whole room from where they stand. NEVER a close-up of "
            "hands or fingers."
            if count > 1 else
            "Produce the single strongest first-person view: what the learner "
            "sees in front of them at that exact moment, the setting clearly "
            "recognizable and the feeling palpable. Do NOT focus on hands."
        )
        gender_rule = _gender_rule(user.gender)

        prompt = (
            "You create reminder assets for an Episodic Future Thinking study "
            "with university students in a research-methods course. The "
            "participant answered 7 questions about "
            "an imagined future moment (below, answers may be in Persian). "
            + gender_rule +
            f"Produce EXACTLY {count} item(s) as a JSON array. Each item: "
            '{"image_prompt": "...", "cue": "..."}.\n\n'
            "image_prompt rules (write in English, max 75 words): describe a "
            "REALISTIC photographic scene faithful to THIS episode — the "
            "specific place, objects, people and atmosphere the participant "
            "described, seen in FIRST-PERSON, through the learner's own eyes, "
            "as if they were holding the camera at eye level. The learner is "
            "therefore naturally out of frame — never describe their face, "
            "their back, or a hidden/cropped face. Do NOT make hands the "
            "subject and never a close-up of hands/fingers. Emphasize the "
            f"setting and the feeling. No readable text or signs. {angle_rule}\n\n"
            "cue rules (write in Persian, max 18 words): one warm "
            "FIRST-PERSON sentence in the participant's own voice (من/دارم/"
            "می‌بینم…), FEELING FIRST then the situation — like «آرام و مطمئنم، "
            "پشت میزم دارم ...». Never address them as «تو»; the sentence must "
            "sound like their own thought. No advice, no quotes.\n\n"
            f"Follow the style of these examples:\n{_FEW_SHOT}\n"
            "Return ONLY the JSON array.\n\nEPISODE ANSWERS:\n" + episode_text
        )
        try:
            raw = _prompt_completion(client, prompt, 900)
            raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                pairs = [p for p in parsed if isinstance(p, dict)][:count]
            _log_prompt(db, user.id, "reminder_set_prompts", prompt, raw)
        except Exception as e:
            print(f"⚠️ Reminder-set prompt generation failed: {e}")

    if not pairs:
        # Deterministic fallback prompts (first-person, learner out of frame).
        base = (
            "Photorealistic photograph, warm natural light, no readable text. "
            "First-person point of view — the camera is the learner's own "
            "eyes at their hopeful future moment of reaching their academic "
            "goal, so "
            "they are naturally out of frame: "
        )
        pairs = [
            {"image_prompt": base + "looking ahead at the people and place of "
             "their goal, calm and inviting.",
             "cue": FALLBACK_CUE},
            {"image_prompt": base + "looking down across their own desk and "
             "the things on it, calm and inviting.",
             "cue": FALLBACK_CUE},
            {"image_prompt": base + "a wide view of the whole room from where "
             "they stand, warm and hopeful.",
             "cue": FALLBACK_CUE},
        ][:count]

    # 2) Generate the images. Uses the long-timeout image client: generation
    # legitimately runs for minutes, and the chat timeout would abort it.
    assets: list[models.ReminderAsset] = []
    img = _image_client()
    if img is not None:
        REMINDERS_DIR.mkdir(parents=True, exist_ok=True)
        for i, pair in enumerate(pairs):
            started = time.time()
            try:
                print(f"🖼️ generating image {i} model={IMAGE_MODEL} …")
                image_bytes = _generate_image_bytes(
                    img,
                    str(pair.get("image_prompt") or "") + IMAGE_STYLE_SUFFIX,
                )
                if not image_bytes:
                    # The call succeeded but carried no usable image — a
                    # provider returning an unexpected payload shape looks
                    # exactly like success unless this is said out loud.
                    print(f"⚠️ Image {i}: response contained no image data "
                          f"after {time.time() - started:.1f}s")
                    continue
                filename = f"user_{user.id}_{i}.png"
                (REMINDERS_DIR / filename).write_bytes(image_bytes)
                print(f"✅ Image {i} saved ({len(image_bytes)} bytes, "
                      f"{time.time() - started:.1f}s) → {filename}")
                assets.append(models.ReminderAsset(
                    user_id=user.id,
                    asset_index=i,
                    image_url=f"/static/reminders/{filename}?v={int(time.time())}",
                    cue=str(pair.get("cue") or FALLBACK_CUE),
                ))
                _log_prompt(db, user.id, f"reminder_image_{i}",
                            str(pair.get("image_prompt")), filename)
            except Exception as e:
                print(f"⚠️ Image {i} generation failed after "
                      f"{time.time() - started:.1f}s: {type(e).__name__}: {e}")
    else:
        print("🖼️ ABORT: no image client — check the key for the active provider")

    print(f"🖼️ reminder-set user={user.id} produced {len(assets)}/{len(pairs)} images")

    # 3) Replace old assets; keep ExtensionReminder pointing at asset 0.
    if assets:
        db.query(models.ReminderAsset).filter(
            models.ReminderAsset.user_id == user.id).delete()
        for a in assets:
            db.add(a)

        reminder = (
            db.query(models.ExtensionReminder)
            .filter(models.ExtensionReminder.user_id == user.id)
            .first()
        )
        if reminder is None:
            reminder = models.ExtensionReminder(
                user_id=user.id,
                image_url=assets[0].image_url, cue=assets[0].cue)
            db.add(reminder)
        else:
            reminder.image_url = assets[0].image_url
            reminder.cue = assets[0].cue
        db.commit()
        for a in assets:
            db.refresh(a)
    return assets


def create_placeholder_reminder(db: Session, user: models.User) -> models.ExtensionReminder:
    """Stores a placeholder image under the user's id — full pipeline test
    (file keyed to user, served via /static, fetched by the extension)
    without any OpenAI cost. Used during work step 8 debugging.
    """
    import shutil

    REMINDERS_DIR.mkdir(parents=True, exist_ok=True)
    src = STATIC_DIR / "placeholder_reminder.png"
    dst = REMINDERS_DIR / f"user_{user.id}.png"
    if src.exists():
        shutil.copyfile(src, dst)
    image_url = f"/static/reminders/user_{user.id}.png?v={int(time.time())}"

    reminder = (
        db.query(models.ExtensionReminder)
        .filter(models.ExtensionReminder.user_id == user.id)
        .first()
    )
    if reminder is None:
        reminder = models.ExtensionReminder(user_id=user.id, image_url=image_url)
        db.add(reminder)
    else:
        reminder.image_url = image_url
    reminder.cue = FALLBACK_CUE

    db.commit()
    db.refresh(reminder)
    return reminder


def generate_reminder(db: Session, user: models.User) -> models.ExtensionReminder:
    """Creates/updates the user's ExtensionReminder from their EFT episode.

    Never raises: on failure the existing (or placeholder) values are kept.
    """
    fields = _latest_episode_fields(db, user.id)

    reminder = (
        db.query(models.ExtensionReminder)
        .filter(models.ExtensionReminder.user_id == user.id)
        .first()
    )
    if reminder is None:
        reminder = models.ExtensionReminder(
            user_id=user.id,
            image_url=f"https://picsum.photos/seed/moirai-user-{user.id}/900/600",
            cue=FALLBACK_CUE,
        )
        db.add(reminder)

    cue = generate_cue(db, user.id, fields)
    if cue:
        reminder.cue = cue

    image_url = generate_image(db, user.id, fields)
    if image_url:
        reminder.image_url = image_url

    db.commit()
    db.refresh(reminder)
    return reminder




# ─────────────────────────────────────────────────────────────────────
# GENERIC (CONTROL) REMINDERS — the comparison arm
# ─────────────────────────────────────────────────────────────────────
# A small SET of encouraging, non-personal reminders, identical for every
# participant, shown instead of the personalized ones on a configurable
# fraction of triggers.
#
# These SHIP WITH THE CODE (app/static/generic/), generated once ahead of
# time by scripts/generate_generic_images.py. They are not participant data
# and not written at runtime, which is what makes them a usable control:
#   - every participant sees the identical set, on every deploy;
#   - they cannot vanish when the container is rebuilt;
#   - nothing is generated during a session, so nobody waits;
#   - generating them needs a provider that can be reached from a laptop,
#     which the deployed server cannot do anyway.
#
# Same model, size, quality and style suffix as the personalized images, and
# the same number of them, so the two arms differ ONLY in whether the scene
# is the participant's own. A cheaper-looking or more repetitive control
# would make the comparison about that instead of personalization.
#
# Content is deliberately empty of specifics — no people, no named place, no
# goal, no outcome — so it cannot resemble one participant's episode more
# closely than another's.
GENERIC_DIR = BUNDLED_STATIC_DIR / "generic"

GENERIC_PROMPTS = [
    ("A calm, encouraging photograph of an inviting empty study space in warm "
     "natural morning light: a wooden desk by a window, a closed notebook and "
     "a pen, a cup of tea, a small plant, soft daylight across the surface. "
     "No people at all, no faces, no readable text anywhere."),
    ("A quiet, hopeful photograph of an empty library reading area in soft "
     "afternoon light: a long wooden table, a chair pulled slightly out, "
     "shelves blurred in the background, a window with warm light. No people "
     "at all, no faces, no readable text anywhere."),
    ("A peaceful photograph of an empty café table by a window in gentle "
     "daylight: a warm drink, a folded scarf on the chair back, a street "
     "softly out of focus outside. No people at all, no faces, no readable "
     "text anywhere."),
]

# One cue per image, paired by index. THE CONTROL CONDITION.
#
# NEUTRAL TASK MESSAGES. Calm, short, present-tense, about the task in front
# of the participant and nothing else.
#
# Two things they must never be, and both were true of earlier versions:
#
#   NOT FUTURE-ORIENTED. "Remember where you are heading" is a diluted form of
#   the very manipulation being tested — a control participant reading it is
#   doing weak future self-projection, which shrinks the contrast and makes a
#   null result uninterpretable.
#
#   NOT MOTIVATIONAL. "You're making great progress", "don't waste time" turn
#   the control into a second treatment, and a shaming register would make it
#   an actively worse one.
#
# Length is held roughly comparable to the personalized cues so the arms
# differ in content, not in how much text arrives.
GENERIC_CUES = [
    "مطالعه را از همین بخش ادامه بده.",
    "وقتی آماده‌ای، بخش بعدی متن را ادامه بده.",
    "می‌تونی از همین‌جا به خواندن متن برگردی.",
]

GENERIC_PREFIX = "generic_reminder"


def generic_paths() -> list[Path]:
    """Where the shipped control images live, in a fixed order."""
    return [GENERIC_DIR / f"{GENERIC_PREFIX}_{i}.png"
            for i in range(len(GENERIC_PROMPTS))]


def generic_reminders() -> list[dict]:
    """The shipped control set as [{image_url, cue, is_generic}].

    Reads from disk only — never generates. A missing set means the control
    condition silently disappears and every trigger shows the personalized
    image, so absence is stated loudly rather than passed over.
    """
    out = []
    for i, path in enumerate(generic_paths()):
        if path.exists() and path.stat().st_size > 0:
            out.append({
                "image_url": f"/static/generic/{path.name}",
                "cue": GENERIC_CUES[i % len(GENERIC_CUES)],
                "is_generic": True,
            })
    if not out:
        print("⚠️ CONTROL ARM MISSING: no generic reminder images in "
              f"{GENERIC_DIR}. Every trigger will show the personalized "
              "image, so there is no comparison condition. Generate them "
              "with scripts/generate_generic_images.py and commit them.")
    return out


def build_generic_images(overwrite: bool = False) -> list[Path]:
    """Generates the control set into GENERIC_DIR.

    Run from a machine that can reach the image provider (see
    scripts/generate_generic_images.py); never called during a session.
    """
    img = _image_client()
    if img is None:
        raise RuntimeError(
            "No image client — set the API key for the active provider "
            "(check the 'LLM provider=' line printed at startup)."
        )
    GENERIC_DIR.mkdir(parents=True, exist_ok=True)
    made = []
    for prompt, path in zip(GENERIC_PROMPTS, generic_paths()):
        if path.exists() and path.stat().st_size > 0 and not overwrite:
            print(f"• {path.name} already exists — skipping "
                  f"(pass --overwrite to replace)")
            made.append(path)
            continue
        started = time.time()
        print(f"• generating {path.name} with {IMAGE_MODEL} …")
        data = _generate_image_bytes(img, prompt + IMAGE_STYLE_SUFFIX)
        if not data:
            raise RuntimeError(f"{path.name}: response contained no image data")
        path.write_bytes(data)
        print(f"  ✅ {len(data)} bytes in {time.time() - started:.1f}s")
        made.append(path)
    return made
