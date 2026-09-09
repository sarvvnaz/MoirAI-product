#!/usr/bin/env python3
"""Generates the generic (control) reminder images, once, ahead of time.

Run this on a machine that can reach the image provider — the deployed server
cannot reach OpenAI at all, which is one reason these are not generated there.
The output goes to Backend/app/static/generic/ and is COMMITTED, so every
deploy serves the identical control set to every participant.

    cd Backend
    LLM_PROVIDER=openai IMAGE_MODEL=gpt-image-1 python scripts/generate_generic_images.py

    --overwrite   replace images that already exist

Re-running without --overwrite is safe: existing files are skipped. Only
regenerate deliberately — changing the control images mid-study means
different participants saw different stimuli in the same condition.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import describe_llm  # noqa: E402
from app.services.image_service import (  # noqa: E402
    GENERIC_CUES,
    GENERIC_DIR,
    build_generic_images,
)


def main() -> int:
    overwrite = "--overwrite" in sys.argv
    print(f"🧠 {describe_llm()}")
    print(f"📁 output: {GENERIC_DIR}\n")

    try:
        made = build_generic_images(overwrite=overwrite)
    except Exception as e:
        print(f"\n❌ {type(e).__name__}: {e}")
        print("\nIf this is a timeout or connection error, the provider is "
              "unreachable from here — these need a network that can reach it.")
        return 1

    print(f"\n✅ {len(made)} control image(s) in {GENERIC_DIR}")
    for i, p in enumerate(made):
        size = p.stat().st_size if p.exists() else 0
        print(f"   {p.name}  {size:>8,} bytes   cue: {GENERIC_CUES[i]}")
    print("\nLook at them before committing: they must contain no people, no "
          "readable text, and nothing that resembles any particular "
          "participant's imagined scene.")
    print("Then: git add Backend/app/static/generic && git commit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
