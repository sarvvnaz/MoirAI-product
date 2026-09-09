#!/usr/bin/env python3
"""Readable summary of the study database, live from the server.

    export ADMIN_EXPORT_KEY=...            # same value as the server env var
    python scripts/inspect_db.py                       # summary
    python scripts/inspect_db.py --participant 3       # one participant
    python scripts/inspect_db.py --conditions          # personalized vs generic
    python scripts/inspect_db.py --host http://127.0.0.1:8000

Reads through the export API rather than the database file, so it needs no
shell on the server and works the same locally or against production.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

DEFAULT_HOST = "https://moirai-fastapi.chbkn.dev"


def fetch(host: str, key: str) -> dict:
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/research/export",
        headers={"X-Export-Key": key},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 403:
            sys.exit("403 — ADMIN_EXPORT_KEY does not match the server's value.")
        raise


def summary(d: dict) -> None:
    print(f"exported at {d.get('exported_at')}\n")
    for name, rows in d.items():
        if isinstance(rows, list):
            print(f"  {len(rows):>5}  {name}")

    users = d.get("users", [])
    if users:
        print("\nParticipants")
        episodes = {e["user_id"] for e in d.get("eft_episodes", [])}
        profiles = {p["user_id"] for p in d.get("participant_profiles", [])}
        assets = {a["user_id"] for a in d.get("reminder_assets", [])}
        for u in users:
            uid = u["id"]
            flags = "".join([
                "P" if uid in profiles else "·",
                "E" if uid in episodes else "·",
                "I" if uid in assets else "·",
            ])
            print(f"  #{uid:<3} {u.get('participant_code','?'):<12} "
                  f"[{flags}]  imp={u.get('importance', '-')}  "
                  f"{u.get('created_at','')[:16]}")
        print("  legend: P=profile  E=episode  I=image   (· = missing)")


def conditions(d: dict) -> None:
    """Which arm participants actually SAW, per trigger."""
    events = d.get("research_events", [])
    shown = [e for e in events if e.get("reminder_shown_timestamp")]
    counts: dict = {}
    for e in shown:
        counts[e.get("condition_assigned")] = \
            counts.get(e.get("condition_assigned"), 0) + 1

    print(f"triggers logged      : {len(events)}")
    print(f"reminders shown      : {len(shown)}")
    if not shown:
        print("\nNo reminder has been shown yet — nothing to compare.")
        return
    for cond, n in sorted(counts.items()):
        print(f"  {cond or '(unset)':<14} {n:>4}  ({100*n/len(shown):.0f}%)")
    if len(counts) < 2:
        print("\n⚠️  Only one condition appears. Check NEUTRAL_RATIO and that "
              "the generic images are present, or there is no comparison.")


def participant(d: dict, uid: int) -> None:
    for u in d.get("users", []):
        if u["id"] == uid:
            print(json.dumps(u, ensure_ascii=False, indent=2))
            break
    else:
        sys.exit(f"no participant with id {uid}")

    for ep in d.get("eft_episodes", []):
        if ep["user_id"] == uid:
            print("\nEpisode:")
            try:
                fields = json.loads(ep["episode_json"])
            except Exception:
                print(ep["episode_json"][:2000]); continue
            for k, v in fields.items():
                if k.startswith("_history"):
                    continue
                print(f"  {k:<12} {v}")

    imgs = [a for a in d.get("reminder_assets", []) if a["user_id"] == uid]
    if imgs:
        print("\nReminder assets:")
        for a in imgs:
            tag = "generic" if a.get("is_generic") else "personalized"
            print(f"  [{tag}] {a['image_url']}")
            print(f"          cue: {a.get('cue')}")



def measures(d: dict) -> None:
    """Baseline -> closing change per participant, which is the analysis."""
    arms = {u["id"]: u.get("study_group") for u in d.get("users", [])}
    rows = d.get("measure_responses", [])
    if not rows:
        print("No measure responses yet.")
        return

    by = {}
    for r in rows:
        by.setdefault((r["user_id"], r["timepoint"]), {})[r["item_code"]] = r["value"]

    def mean(uid, tp, prefix):
        vals = [v for k, v in by.get((uid, tp), {}).items()
                if k.startswith(prefix) and v is not None]
        return sum(vals) / len(vals) if vals else None

    print(f"{'user':<6}{'arm':<9}{'FSC base':>9}{'FSC end':>9}{'Δ FSC':>8}"
          f"{'INT base':>10}{'INT end':>9}{'Δ INT':>8}")
    for uid in sorted(arms):
        fb, fc = mean(uid, "baseline", "fsc"), mean(uid, "closing", "fsc")
        ib, ic = mean(uid, "baseline", "intent"), mean(uid, "closing", "intent")
        def fmt(x): return f"{x:.2f}" if x is not None else "-"
        def delta(a, b): return f"{b - a:+.2f}" if (a is not None and b is not None) else "-"
        print(f"{uid:<6}{str(arms[uid]):<9}{fmt(fb):>9}{fmt(fc):>9}{delta(fb, fc):>8}"
              f"{fmt(ib):>10}{fmt(ic):>9}{delta(ib, ic):>8}")

    incomplete = [u for u in arms
                  if not by.get((u, "baseline")) or not by.get((u, "closing"))]
    if incomplete:
        print(f"\n⚠️  no change score for users {incomplete} — missing a "
              f"baseline or closing measurement, so they cannot enter the "
              f"pre/post analysis.")



def provenance(d: dict) -> None:
    """The audit trail: when each participant did what, and for how long.

    Not a proof on its own — proof of real participants rests on ethics
    approval and a recruitment log kept outside the dataset. This is the
    corroboration: timestamps a supervisor can inspect, and the timing
    VARIANCE that distinguishes real sessions from fabricated ones.

    Deliberately contains no IP addresses or device identifiers. The consent
    promises full anonymity, and collecting identifiers to prove authenticity
    would break the promise it was meant to support.
    """
    users = {u["id"]: u for u in d.get("users", [])}
    sessions: dict = {}
    for s_ in d.get("sessions", []):
        sessions.setdefault(s_["user_id"], []).append(s_)
    events: dict = {}
    for e in d.get("research_events", []):
        events[e["participant_id"]] = events.get(e["participant_id"], 0) + 1
    episodes: dict = {}
    for ep in d.get("eft_episodes", []):
        episodes[ep["user_id"]] = len(ep.get("episode_json") or "")
    measures: dict = {}
    for m in d.get("measure_responses", []):
        measures[m["user_id"]] = measures.get(m["user_id"], 0) + 1

    def dur(s_):
        a, b = s_.get("started_at"), s_.get("ended_at")
        if not a or not b:
            return None
        from datetime import datetime
        try:
            t0 = datetime.fromisoformat(a.replace("Z", "+00:00"))
            t1 = datetime.fromisoformat(b.replace("Z", "+00:00"))
            return (t1 - t0).total_seconds() / 60
        except Exception:
            return None

    print(f"{'id':<4}{'arm':<9}{'signed up':<17}{'sessions':>9}"
          f"{'minutes':>18}{'events':>8}{'measures':>9}{'episode chars':>14}")
    all_durs = []
    for uid in sorted(users):
        ss = sessions.get(uid, [])
        ds = [x for x in (dur(s_) for s_ in ss) if x is not None]
        all_durs += ds
        mins = ", ".join(f"{x:.0f}" for x in ds) or "-"
        print(f"{uid:<4}{str(users[uid].get('study_group')):<9}"
              f"{(users[uid].get('created_at') or '')[:16]:<17}"
              f"{len(ss):>9}{mins:>18}{events.get(uid, 0):>8}"
              f"{measures.get(uid, 0):>9}{episodes.get(uid, 0):>14}")

    print(f"\n  participants: {len(users)}")
    if all_durs:
        lo, hi = min(all_durs), max(all_durs)
        mean = sum(all_durs) / len(all_durs)
        print(f"  session length: min {lo:.1f}  mean {mean:.1f}  max {hi:.1f} min")
        if hi - lo < 0.5 and len(all_durs) > 2:
            print("  ⚠️  session lengths are nearly identical — real sessions "
                  "vary. Worth checking these are not test runs.")
    dates = sorted((u.get("created_at") or "")[:10] for u in users.values() if u.get("created_at"))
    if dates:
        print(f"  collection window: {dates[0]} → {dates[-1]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.getenv("MOIRAI_HOST", DEFAULT_HOST))
    ap.add_argument("--key", default=os.getenv("ADMIN_EXPORT_KEY"))
    ap.add_argument("--participant", type=int)
    ap.add_argument("--conditions", action="store_true")
    ap.add_argument("--measures", action="store_true")
    ap.add_argument("--provenance", action="store_true")
    ap.add_argument("--raw", action="store_true", help="dump the full JSON")
    a = ap.parse_args()

    if not a.key:
        sys.exit("Set ADMIN_EXPORT_KEY (env or --key) to the server's value.")

    d = fetch(a.host, a.key)
    if a.raw:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    elif a.participant is not None:
        participant(d, a.participant)
    elif a.conditions:
        conditions(d)
    elif a.measures:
        measures(d)
    elif a.provenance:
        provenance(d)
    else:
        summary(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
