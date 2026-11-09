#!/usr/bin/env python3
"""Builds a browsable HTML report of the study, and opens it.

    cd Backend
    ADMIN_EXPORT_KEY=... python3 scripts/report.py
    ADMIN_EXPORT_KEY=... python3 scripts/report.py --host http://127.0.0.1:8000
    ADMIN_EXPORT_KEY=... python3 scripts/report.py --no-open -o /tmp/study.html

Reads the same export API as inspect_db.py, so it needs no database access
and works against production from a laptop. Images are referenced by URL on
the server, so the page must be viewed while the server is reachable.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime
from pathlib import Path

DEFAULT_HOST = "https://moirai.telab.ir"

# The 7 EFT fields, in the order they are asked, with Persian labels so the
# episode reads as a scene rather than a dict dump.
EPISODE_FIELDS = [
    ("goal", "هدف"), ("when", "زمان"), ("where", "مکان"),
    ("action", "کار"), ("objects", "اطراف"), ("who", "افراد"),
    ("feeling", "احساس"),
]


def fetch(host: str, key: str) -> dict:
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/research/export",
        headers={"X-Export-Key": key})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            sys.exit("403 — ADMIN_EXPORT_KEY does not match the server.")
        raise
    except urllib.error.URLError as e:
        sys.exit(f"Could not reach {host}: {e.reason}")


def e(v) -> str:
    return html.escape(str(v)) if v is not None else ""


def bar(pct: float, color: str) -> str:
    return (f'<div class="bar"><div class="fill" style="width:{pct:.1f}%;'
            f'background:{color}"></div></div>')


def delivery_audit(events: list, diseng: list, n_users: int) -> str:
    """Did the protocol actually run? Check this BEFORE looking at any result.

    Three ways the study can fail while every chart still renders:

      · dosage — someone got one cue instead of two, so their row breaks the
        equal-exposure assumption the whole design rests on;
      · state split — if nearly every cue lands in one state, one of the two
        primary measures has almost no data, and no amount of analysis
        recovers it;
      · lateness — "the cue fired at minute 10" is a claim, and
        delivery_offset_ms is the only thing that checks it.
    """
    per_user: dict = {}
    for ev in events:
        per_user.setdefault(ev.get("participant_id"), []).append(ev)

    delivered = [e_ for e_ in events if e_.get("delivered_at")]
    states = Counter(e_.get("state_at_delivery") or "(none)"
                     for e_ in delivered)
    reasons = Counter(e_.get("not_delivered_reason") for e_ in events
                      if e_.get("not_delivered_reason"))

    full_dose = sum(1 for rows in per_user.values()
                    if len([r for r in rows if r.get("delivered_at")]) == 2)
    under = len(per_user) - full_dose

    offsets = [e_.get("delivery_offset_ms") or 0 for e_ in delivered]
    worst = max(offsets) if offsets else 0
    median = sorted(offsets)[len(offsets) // 2] if offsets else 0

    # The two primary measures, and how many rows each actually has.
    n_latency = len([e_ for e_ in delivered
                     if e_.get("return_latency_ms") is not None])
    n_retention = len([e_ for e_ in delivered
                       if e_.get("post_cue_focus_seconds") is not None])

    rows = ""
    for label, n, colour in (
            ("active (corner card)", states.get("active", 0), "#7c6cf0"),
            ("idle (in-app overlay)", states.get("idle", 0), "#f0b429"),
            ("off tab (modal)", states.get("off_tab", 0), "#38c9a5"),
            ("off browser (modal)", states.get("off_browser", 0), "#4a9ede")):
        pct = 100 * n / (len(delivered) or 1)
        rows += (f'<tr><td>{label}</td><td class="num">{n}</td>'
                 f'<td class="barcell">{bar(pct, colour)}</td>'
                 f'<td class="num">{pct:.0f}%</td></tr>')

    warns = ""
    if under:
        warns += (f'<p class="warn">⚠️ {under} of {len(per_user)} participants '
                  f'did NOT receive both cues. Equal dosage is the claim the '
                  f'design rests on — see the reasons below before analysing '
                  f'anything.</p>')
    if delivered and min(n_latency, n_retention) == 0:
        warns += ('<p class="warn">⚠️ One of the two primary measures has NO '
                  'rows. Return latency needs cues delivered off-tab and '
                  'retention needs cues delivered while active; if every cue '
                  'lands in one state, only one question can be answered.</p>')
    if worst > 60_000:
        warns += (f'<p class="warn">⚠️ Worst delivery was {worst/1000:.0f}s '
                  f'late. The MV3 alarm floor explains up to ~30s; beyond '
                  f'that the schedule is not being honoured.</p>')

    reason_rows = "".join(
        f'<tr><td>{e(k)}</td><td class="num">{v}</td></tr>'
        for k, v in reasons.most_common()) or (
        '<tr><td class="muted">none — every slot delivered</td>'
        '<td class="num">0</td></tr>')

    closed = [x for x in diseng if x.get("ended_at")]
    open_eps = len(diseng) - len(closed)
    diseng_warn = ""
    if open_eps:
        diseng_warn = (f'<p class="warn">⚠️ {open_eps} disengagement '
                       f'episode(s) never closed, so their duration is NULL '
                       f'and they drop silently out of time-on-task.</p>')

    return f"""
<h2>Delivery audit <span class="muted" style="font-size:13px">
 (check this before reading any result)</span></h2>
{warns}
<div class="stats">
 <div class="stat"><b>{full_dose}/{len(per_user)}</b><span>got both cues</span></div>
 <div class="stat"><b>{n_latency}</b><span>return-latency rows</span></div>
 <div class="stat"><b>{n_retention}</b><span>retention rows</span></div>
 <div class="stat"><b>{median/1000:.1f}s</b><span>median lateness</span></div>
 <div class="stat"><b>{worst/1000:.1f}s</b><span>worst lateness</span></div>
</div>

<h3>State when the cue landed</h3>
<p class="muted">This split decides how much data each primary measure gets.
 It cannot be chosen — only observed.</p>
<table>{rows}</table>

<h3 style="margin-top:22px">Undelivered slots, by reason</h3>
<p class="muted">grace_expired = the cue was due and delivery failed ·
 session_ended_before_slot = the participant finished early and is
 under-dosed · no_asset_available = no stimulus existed for that slot</p>
<table>{reason_rows}</table>

<h3 style="margin-top:22px">Disengagement episodes</h3>
{diseng_warn}
<p class="muted">{len(diseng)} episode(s) · {len(closed)} closed ·
 {Counter(x.get('episode_type') for x in diseng).most_common()}</p>
"""


def build(d: dict, host: str) -> str:
    users = d.get("users", [])
    episodes = {ep["user_id"]: ep for ep in d.get("eft_episodes", [])}
    profiles = {p["user_id"] for p in d.get("participant_profiles", [])}
    # The scheduled-cue tables. research_events is FROZEN — it holds rows from
    # the reactive protocol and must never be pooled with these, so it is not
    # read here at all.
    events = d.get("cue_deliveries", [])
    diseng = d.get("disengagement_episodes", [])
    sessions = d.get("sessions", [])

    assets_by_user: dict = {}
    for a in d.get("reminder_assets", []):
        assets_by_user.setdefault(a["user_id"], []).append(a)

    events_by_user: dict = {}
    for ev in events:
        events_by_user.setdefault(ev.get("participant_id"), []).append(ev)

    shown = [ev for ev in events if ev.get("delivered_at")]
    conds = Counter(ev.get("condition") or "(unset)" for ev in shown)
    n_shown = len(shown) or 1

    # ── condition split: the number the whole comparison rests on ──
    cond_rows = ""
    for name, colour in (("personalized", "#7c6cf0"), ("neutral", "#38c9a5")):
        n = conds.get(name, 0)
        cond_rows += (
            f'<tr><td>{name}</td><td class="num">{n}</td>'
            f'<td class="barcell">{bar(100 * n / n_shown, colour)}</td>'
            f'<td class="num">{100 * n / n_shown:.0f}%</td></tr>')

    warn = ""
    if not shown:
        warn = ('<p class="warn">No reminder has been shown yet — there is '
                'nothing to compare.</p>')
    elif len([c for c in conds if c in ("personalized", "neutral")]) < 2:
        warn = ('<p class="warn">⚠️ Only one condition appears. Either every '
                'participant so far landed in one arm, or the generic images '
                'are missing — as it stands there is no control arm.</p>')

    # ── participants ──
    cards = ""
    for u in sorted(users, key=lambda x: x["id"]):
        uid = u["id"]
        ep = episodes.get(uid)
        assets = assets_by_user.get(uid, [])
        uevents = events_by_user.get(uid, [])
        ushown = [x for x in uevents if x.get("delivered_at")]
        ucond = Counter(x.get("condition") or "?" for x in ushown)

        chips = "".join(
            f'<span class="chip {"ok" if cond else "miss"}">{label}</span>'
            for label, cond in (
                ("profile", uid in profiles),
                ("episode", ep is not None),
                ("image", any(not a.get("is_generic") for a in assets)),
            ))

        fields = {}
        history = []
        if ep:
            try:
                parsed = json.loads(ep["episode_json"])
                fields = parsed
                history = parsed.get("_history") or []
            except Exception:
                fields = {}

        ep_html = ""
        for key, label in EPISODE_FIELDS:
            val = fields.get(key)
            if val:
                ep_html += (f'<div class="row"><div class="k">{label}</div>'
                            f'<div class="v">{e(val)}</div></div>')
        summary = fields.get("_summary")
        if summary:
            ep_html += (f'<div class="row"><div class="k">خلاصه</div>'
                        f'<div class="v summary">{e(summary)}</div></div>')
        importance = fields.get("importance")
        if importance:
            ep_html += (f'<div class="row"><div class="k">اهمیت</div>'
                        f'<div class="v">{e(importance)} / 6</div></div>')
        if not ep_html:
            ep_html = '<p class="muted">No episode recorded.</p>'

        imgs = ""
        for a in assets:
            tag = "generic" if a.get("is_generic") else "personalized"
            url = a["image_url"]
            if url.startswith("/"):
                url = host.rstrip("/") + url
            imgs += (f'<figure><img loading="lazy" src="{e(url)}" alt="">'
                     f'<figcaption><b>{tag}</b><br>{e(a.get("cue") or "")}'
                     f'</figcaption></figure>')
        if not imgs:
            imgs = '<p class="muted">No reminder image generated.</p>'

        convo = ""
        for m in history:
            if not isinstance(m, dict):
                continue
            who = "participant" if m.get("role") == "user" else "guide"
            convo += (f'<div class="msg {who}"><span>{e(m.get("content"))}'
                      f'</span></div>')
        convo_block = (f'<details><summary>Conversation '
                       f'({len(history)} messages)</summary>'
                       f'<div class="convo">{convo}</div></details>'
                       if convo else "")

        cards += f"""
        <section class="card">
          <header>
            <h3>#{uid} · {e(u.get('participant_code'))}</h3>
            <div>{chips}</div>
          </header>
          <div class="meta">
            joined {e((u.get('created_at') or '')[:16])}
            · triggers {len(uevents)} · reminders shown {len(ushown)}
            · personalized {ucond.get('personalized', 0)}
            · generic {ucond.get('neutral', 0)}
          </div>
          <div class="cols">
            <div class="episode">{ep_html}</div>
            <div class="images">{imgs}</div>
          </div>
          {convo_block}
        </section>"""

    counts = "".join(
        f'<div class="stat"><b>{len(v)}</b><span>{k}</span></div>'
        for k, v in d.items() if isinstance(v, list))

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>MoirAI study report</title>
<style>
 :root {{ --ink:#1d1b3a; --muted:#6b6890; --line:#e6e4f2; --bg:#f6f5fb; }}
 * {{ box-sizing:border-box }}
 body {{ margin:0; padding:32px; background:var(--bg); color:var(--ink);
   font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Vazirmatn,sans-serif }}
 h1 {{ margin:0 0 4px }} h3 {{ margin:0; font-size:16px }}
 .muted {{ color:var(--muted) }}
 .stats {{ display:flex; gap:12px; flex-wrap:wrap; margin:20px 0 }}
 .stat {{ background:#fff; border:1px solid var(--line); border-radius:12px;
   padding:12px 16px; min-width:120px }}
 .stat b {{ display:block; font-size:22px }}
 .stat span {{ color:var(--muted); font-size:12px }}
 table {{ border-collapse:collapse; background:#fff; border-radius:12px;
   overflow:hidden; width:100%; max-width:620px }}
 td {{ padding:10px 14px; border-top:1px solid var(--line) }}
 .num {{ text-align:right; font-variant-numeric:tabular-nums }}
 .barcell {{ width:55% }}
 .bar {{ background:var(--line); border-radius:6px; height:10px }}
 .fill {{ height:10px; border-radius:6px }}
 .warn {{ background:#fff4e5; border:1px solid #ffd9a0; padding:12px 16px;
   border-radius:10px; max-width:620px }}
 .card {{ background:#fff; border:1px solid var(--line); border-radius:16px;
   padding:20px; margin:16px 0 }}
 .card header {{ display:flex; justify-content:space-between;
   align-items:center; gap:12px; flex-wrap:wrap }}
 .chip {{ font-size:11px; padding:3px 9px; border-radius:999px; margin-left:6px }}
 .chip.ok {{ background:#e3f8f1; color:#1b7f66 }}
 .chip.miss {{ background:#fde8e8; color:#a33 }}
 .meta {{ color:var(--muted); font-size:12.5px; margin:6px 0 14px }}
 .cols {{ display:grid; grid-template-columns:1fr 320px; gap:20px }}
 @media (max-width:900px) {{ .cols {{ grid-template-columns:1fr }} }}
 .row {{ display:grid; grid-template-columns:80px 1fr; gap:10px;
   padding:6px 0; border-top:1px dashed var(--line) }}
 .k {{ color:var(--muted); font-size:13px }}
 .v {{ direction:rtl; text-align:right }}
 .v.summary {{ background:#f2f0ff; padding:8px 10px; border-radius:8px }}
 figure {{ margin:0 0 14px }}
 figure img {{ width:100%; border-radius:10px; display:block; background:var(--line) }}
 figcaption {{ font-size:12px; color:var(--muted); direction:rtl;
   text-align:right; margin-top:6px }}
 details {{ margin-top:14px }}
 summary {{ cursor:pointer; color:var(--muted); font-size:13px }}
 .convo {{ margin-top:10px; max-height:420px; overflow:auto }}
 .msg {{ display:flex; margin:6px 0 }}
 .msg span {{ direction:rtl; text-align:right; padding:8px 12px;
   border-radius:12px; max-width:80%; font-size:13.5px }}
 .msg.participant {{ justify-content:flex-start }}
 .msg.participant span {{ background:#eceaff }}
 .msg.guide {{ justify-content:flex-end }}
 .msg.guide span {{ background:#f2f2f6 }}
</style></head><body>
<h1>MoirAI study report</h1>
<p class="muted">{e(host)} · exported {e(d.get('exported_at',''))[:19]}
 · generated {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>

<div class="stats">{counts}</div>

<h2>Condition split <span class="muted" style="font-size:13px">
 (what participants actually saw)</span></h2>
{warn}
<table>{cond_rows}</table>
<p class="muted">{len(events)} slots scheduled · {len(shown)} cues delivered
 · {len(sessions)} sessions</p>

{delivery_audit(events, diseng, len(users))}

<h2>Participants ({len(users)})</h2>
{cards or '<p class="muted">No participants yet.</p>'}
</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.getenv("MOIRAI_HOST", DEFAULT_HOST))
    ap.add_argument("--key", default=os.getenv("ADMIN_EXPORT_KEY"))
    ap.add_argument("-o", "--out", default="study_report.html")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    if not a.key:
        sys.exit("Set ADMIN_EXPORT_KEY (env or --key).")

    d = fetch(a.host, a.key)
    out = Path(a.out).resolve()
    out.write_text(build(d, a.host), encoding="utf-8")
    print(f"✅ {out}")
    cd = d.get("cue_deliveries", [])
    print(f"   {len(d.get('users', []))} participants, "
          f"{len([c for c in cd if c.get('delivered_at')])}/{len(cd)} "
          f"scheduled cues delivered, "
          f"{len(d.get('disengagement_episodes', []))} disengagement episodes")
    if not a.no_open and sys.platform == "darwin":
        subprocess.run(["open", str(out)], check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
