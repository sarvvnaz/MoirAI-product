# MoirAI Reactive

MoirAI Reactive is a research prototype for studying whether episodic future
thinking (EFT) can help people return to an intended task after disengagement.
The current study applies the intervention to English-language study: a
participant constructs a concrete future episode connected to their goal, and
the system turns that episode into a visual reminder.

The project's main design choice is **reactive timing**. Reminders are not sent
at predetermined times. They appear when the system detects a behavior that may
indicate disengagement: switching away from the study tab or remaining inactive
inside the study application.

## Research question

Does showing a personalized future-self reminder at the moment of
disengagement improve return behavior, future-self continuity, and study
intention compared with showing a generic reminder at the same moment?

This separates two parts of the intervention:

1. **Timing:** both groups receive reminders in the same behavioral contexts.
2. **Content:** only the EFT group receives reminders grounded in the
   participant's own imagined future.

The comparison is therefore personalized EFT content versus generic content,
not reminders versus no reminders.

## Study design

The study uses a balanced between-subjects design. Each participant is assigned
once at registration and remains in the same arm:

| Arm | Preparation | Reminder content |
|---|---|---|
| `eft` | Guided EFT conversation and confirmation of a future episode | AI-generated images and cues based on that participant's episode |
| `control` | No EFT conversation or personal image generation | Shared generic reminders |

The backend enforces condition assignment and only returns assets belonging to
the participant's arm. The browser extension does not randomize conditions.

### Participant flow

1. Consent, anonymous participant ID, and baseline measures.
2. Balanced assignment to the EFT or control arm.
3. EFT episode construction and manipulation check for the EFT arm.
4. Reminder preparation and browser-extension installation.
5. Two study sessions with reactive reminders.
6. Post-session feedback and closing measures.

### Measures and behavioral outcomes

The application records one research event for each `tab_switch` or `idle`
trigger. Behavioral outcomes include:

- whether the participant returned to the reading;
- return latency;
- reading time after returning;
- repeated disengagement after returning;
- reminder dismissal and use of the return button.

Self-report measures include future-self continuity, study intention, the EFT
manipulation check, reminder helpfulness/distraction, goal salience, and an
attention check. Published measures are translated into Persian; study-authored
items are identified separately in the code and must not be reported as
validated scales.

## Intervention behavior

| Trigger | Where the reminder appears | Timing |
|---|---|---|
| Participant switches away from the active study tab or window | Chrome extension overlay | Immediately after the switch, subject to an 8-second anti-spam cooldown |
| Participant remains inactive inside the study app | Flutter overlay | When the configured idle threshold is reached |

The experiment is between-subjects. The backend assigns each participant to
`eft` or `control`, and only returns assets for that arm. The extension rotates
through the returned assets; it does not randomize experimental conditions.

> **Research-build note:** `StudySessionPage.idleThreshold` is currently 10
> seconds for fast testing, while its protocol comment specifies 90 seconds.
> Set and document the final threshold before collecting pilot or study data,
> then rebuild the Flutter web application.

## Components

- `Frontend/` — Flutter application and participant flow.
- `Backend/` — FastAPI API, study data, reminder generation, compiled Flutter
  web build, and the downloadable Chrome extension.
- `Backend/app/static/moirai-extension.zip` — extension installer downloaded
  from the in-app setup screen.
- `Backend/app/static/moirai-extension/` — readable extension source.
- `RUN_PROJECT.md` — expanded local setup and troubleshooting instructions.

FastAPI serves the Flutter build, API, reminder images, and extension from one
origin. This is intentional: Flutter resolves API URLs against the page origin,
and Chrome only accepts external extension messages from origins listed in the
extension manifest.

## Requirements

- macOS, Linux, or Windows with a Unix-compatible shell for the helper scripts
- Python 3.12 or 3.13
- Chrome or another Chromium browser supporting Manifest V3
- Flutter SDK only when rebuilding the frontend

Python 3.14 is not recommended for the pinned dependencies. It may lack a
compatible `pydantic-core` wheel and attempt to install Rust during `pip
install`.

## How to run

### 1. Configure the backend

```bash
cd Backend
cp .env.example app/.env
```

Edit `app/.env`. For a local SQLite run, start with:

```dotenv
DEBUG_MODE=True
DATA_DIR=./data
DATA_PERSISTENT=false
DATABASE_URL=sqlite:///./data/app.db
```

Generate the signing secrets and place them in `app/.env`:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

Use one result for `SECRET_KEY` and the other for `ADMIN_EXPORT_KEY`. Add the
appropriate model-provider key described in `.env.example`.

### 2. Create the environment and start the application

On macOS:

```bash
brew install python@3.12
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>. The backend already contains a compiled Flutter
web build, so Flutter is not required for this first run.

### 3. Install and connect the extension

The participant flow includes an extension setup page. It downloads
`/static/moirai-extension.zip` from the same backend that served the app.

1. Click **Download extension** in the app.
2. Extract the ZIP.
3. Open `chrome://extensions`.
4. Enable **Developer mode**.
5. Select **Load unpacked** and choose the extracted `moirai-extension` folder.
6. Return to the app.

The page checks for the extension every four seconds and sends the logged-in
participant token when it becomes available. Chrome does not permit a normal
website to silently install an unpacked extension, so the **Load unpacked** step
cannot be automated.

The manifest key and Flutter client both resolve to this stable extension ID:

```text
kpkfnoihiigfebpojgabfkbippafdhah
```

### 4. Verify the integration

After signing in and reaching a study session:

1. Confirm the setup page reports that the extension is connected.
2. Switch to another tab and verify that the extension reminder appears.
3. Return to the study, remain inactive for the configured threshold, and
   verify that the in-app reminder appears.
4. Inspect the backend data export or database for corresponding
   `tab_switch`, `idle`, `reminder_shown`, and return data.

## Relevant backend contract

The extension uses these existing endpoints:

- `GET /api/extension/reminder-set` — fetch the participant's assigned assets.
- `GET /api/extension/status` — recover active-session state after a service
  worker restart.
- `POST /api/extension/session` — set active/inactive study-session state.
- `POST /api/research/event/reminder-shown` — record what was displayed.
- `POST /api/research/event/return` — record return to the study.

There are no scheduled cue or disengagement endpoints in this version.

## Rebuilding the frontend

Flutter should still be served through FastAPI for local integration testing.
Running it on a separate port without a proxy makes it call the wrong origin.

```bash
cd Backend
PUB_OFFLINE=0 ./scripts/build_web.sh
```

The script builds `Frontend/` and replaces `Backend/app/web/`.

## Deployment package

Build a clean backend upload after rebuilding Flutter:

```bash
cd Backend
./scripts/package_deploy.sh
```

For an unchanged frontend build:

```bash
SKIP_WEB=1 ./scripts/package_deploy.sh
```

The deploy archive is written to `Backend/dist/moirai-deploy.zip`. Runtime data
must be mounted at the path configured by `DATA_DIR`; otherwise redeployment
will erase the SQLite database and generated reminders.

## Security and repository hygiene

- Never commit `.env`, database files, generated participant reminders, or a
  private extension key.
- Configure production secrets in the hosting platform.
- The public manifest key is intentionally committed because it keeps the
  extension ID stable; it is not the private signing key.
- The root `.gitignore` excludes local environments and large generated build
  directories that previously caused oversized Git pushes.

## Research status and limitations

This repository is an experimental research implementation, not a validated
clinical or educational product. Before formal data collection:

- replace the 10-second development idle threshold with the protocol value;
- complete and verify the full citation for the Asayama manipulation check;
- verify the Persian forward/back translations and document that no validated
  Persian version is claimed;
- test persistence across a real deployment so participant data and reminder
  images survive redeployment;
- freeze the protocol and software version used for the final sample.

## Troubleshooting

### `No space left on device` while installing Rust

Free disk space, remove the failed virtual environment, and recreate it with
Python 3.12. A normal installation should use the published `pydantic-core`
wheel and should not need a Rust toolchain.

### `No module named uvicorn`

The earlier dependency installation failed before Uvicorn was installed.
Activate the Python 3.12 environment and rerun:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8000
```

### Extension does not connect

- Confirm the app is opened at `http://127.0.0.1:8000`, `http://localhost`, or
  one of the HTTPS origins listed in the extension manifest.
- Confirm the extension ID matches the value above.
- Reload the extension and return to the setup screen.
- Check the extension service-worker console in `chrome://extensions`.
