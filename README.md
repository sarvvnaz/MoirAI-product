# MoirAI Product

Persian PDF reading companion based on [MoirAI-reactive](https://github.com/sarvvnaz/MoirAI-reactive). Keeps the original navy, lavender, purple, and mint interface.

Users create an account, describe a personally meaningful future in a guided conversation, receive an AI-generated reminder, and choose their own PDF to read. The browser extension is optional. Research questionnaires and privacy-screen navigation are paused; their source and historical data remain available.

## Current experience

- Concise Persian introduction and account creation.
- Seven conversational steps tied to the user's own long-term goal, with no importance rating or post-chat questionnaire.
- One optional 1–5 conversation rating while the reminder image generates, persisted as `product_feedback` in `UserActivity`.
- Image prompts request natural neck-down framing or softly defocused faces, avoiding identifiable facial details and uncanny masking. Generated results still require visual review.
- PDF selection up to 30 MB, with file-signature validation. Files stay in browser memory and must be selected again after refresh.
- PDF reading without the fixed quiz or exam timer; existing reminder and session completion machinery is retained.
- Bundled Vazirmatn font, with its OFL license.

## Run locally

Use Python 3.12 and Flutter. In `Backend`, create a virtual environment and install `requirements.txt`. Copy `.env.example` to `app/.env`, set signing secrets and provider credentials, and choose an image model available to that account. The local product configuration was verified with `IMAGE_MODEL=gpt-image-2`; keep real credentials outside Git.

From `Frontend`, run `flutter pub get` and `flutter build web --release --pwa-strategy=none`. Copy `Frontend/build/web/` into `Backend/app/web/`, then run `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from `Backend`. Serve frontend and API from the same origin.

For local SQLite, configure `DEBUG_MODE=True`, a local `DATA_DIR`, and `DATABASE_URL`. For deployment, use persistent storage for the database and generated reminders. The existing `RUN_PROJECT.md` contains additional setup details inherited from the research version.

## Validation

`python -m pytest Backend/tests/test_demo_flow.py -q` covers product routing, signup without profile collection, chatbot step boundaries, and feedback persistence. `flutter test test/pdf_validation_test.dart` covers PDF validation. The older research-specific tests remain as reference and are not all updated for the product flow.

This is an incremental product build. Session records and research infrastructure are retained; accounts currently resume through one completed reading session. Documents and reader position are not stored across refreshes.
