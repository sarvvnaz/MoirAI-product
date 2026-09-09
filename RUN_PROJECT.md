# Run MoirAI locally

The backend serves the compiled Flutter web app and the browser-extension ZIP
from one origin. Use Python 3.12 or 3.13; Python 3.14 may try to compile
`pydantic-core` with Rust and is the cause of the installation failure shown in
the earlier log.

## 1. Configure the backend

```bash
cd Backend
cp .env.example app/.env
```

For local testing, edit `app/.env` and set:

```dotenv
DEBUG_MODE=True
DATA_DIR=./data
DATA_PERSISTENT=false
DATABASE_URL=sqlite:///./data/app.db
```

Add the required API and signing keys described in `.env.example`.

## 2. Install and start

On macOS:

```bash
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. Do not launch Flutter on another port for this
test: the web app intentionally uses its own origin as the API origin.

## 3. Install and connect the extension

During the participant flow, the extension setup screen downloads:

```text
/static/moirai-extension.zip
```

Extract it, open `chrome://extensions`, enable **Developer mode**, choose
**Load unpacked**, and select the extracted `moirai-extension` directory. Return
to the app. The page checks every four seconds and connects the extension using
the logged-in participant token; the manual connection button can retry it.

The extension ID is fixed as `kpkfnoihiigfebpojgabfkbippafdhah` in both the
manifest and Flutter code.

## Intervention timing

- Switching away from the study tab or window during an active session shows
  the extension nudge immediately, subject only to its anti-spam cooldown.
- Remaining idle inside the study app shows the Flutter in-app nudge.
- No scheduled cue or disengagement endpoints are used.

## Rebuild the Flutter web app

Only needed after changing Flutter source:

```bash
cd Backend
PUB_OFFLINE=0 ./scripts/build_web.sh
```

The script builds `Frontend` and copies the result to `Backend/app/web`, where
FastAPI serves it.
