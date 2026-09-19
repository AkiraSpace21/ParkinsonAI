# Parkinson Voice Screening — professional research UI

A clinical-research-styled frontend built around your existing ML pipeline,
with a FastAPI layer replacing the original Gradio interface so the frontend
has full control over layout, mic recording, and waveform visualization.

## Architecture

```
Browser (frontend/, static HTML/CSS/JS)
        │  fetch() → multipart audio upload
        ▼
FastAPI backend (backend/main.py)
        │  calls
        ▼
voice_pipeline.py  — SAME feature extraction, quality gate, imputation,
                      scaling, and model call as your original app.py.
                      Only the return type changed: a structured dict
                      instead of a markdown string.
        │  loads
        ▼
pd_model.joblib / pd_scaler.joblib / pd_model_features.joblib / pd_model_median.joblib
```

`app.py` (your original Gradio interface) is untouched in your uploads and is
no longer used by this version — `voice_pipeline.py` contains the same logic,
refactored to return data instead of a markdown string. If you want to diff
them, the extraction functions (`parkinson_features`, `spectral_and_mfcc_features`,
`check_quality`) are byte-for-byte the same computations, just relocated.

## What changed vs. your original backend, and why

1. **`predict()` → `run_screening()` returns structured data, not markdown.**
   Your original function computed jitter/shimmer/HNR/F0 internally but only
   ever returned a formatted string — the numbers never left the function. The
   "Voice Analysis Summary" cards in the brief need real numbers, so
   `run_screening()` now returns them as a dict. No extraction logic changed.
2. **Microphone recording added.** The original Gradio `gr.Audio` only accepted
   `sources=["upload"]`. The frontend now records directly via the browser's
   `MediaRecorder` API and sends the captured audio to the same backend
   pipeline — no change to how the model consumes audio.
3. **Nothing about feature names, the model, the scaler, or the imputation
   logic was changed, retrained, or invented.**

## Running it

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** — the backend serves the frontend directly,
so there's nothing separate to run. (If you'd rather serve the frontend from
somewhere else, e.g. a CDN, point `API_BASE` in `frontend/js/api.js` at your
backend's URL and enable CORS for that origin in `main.py`.)

## About the four .joblib files

**Your real artifacts (`pd_model.joblib`, `pd_scaler.joblib`,
`pd_model_features.joblib`, `pd_model_median.joblib`) were not included in
what you uploaded**, so this build ships with placeholder versions generated
by `backend/generate_placeholder_artifacts.py` — a logistic regression fit on
random synthetic data, using a plausible feature subset. Its predictions are
meaningless; it exists only so the full pipeline (extraction → impute → scale
→ predict → JSON → UI) is exercisable end-to-end right now.

**To go live:** delete the four placeholder `.joblib` files in `backend/` and
copy in your real ones (same filenames, produced by your `train_final_model.py`).
Nothing else needs to change — `voice_pipeline.py` loads whatever
`pipeline.selected_features` says and adapts automatically. The five
biomarker cards (F0 mean/variability, jitter, shimmer, HNR) will display real
values as long as your real `parkinson_features()` output includes them,
which it does in your original code.

## What I could not test in this environment

I don't have network access here, so `librosa`, `parselmouth`, `xgboost`,
`fastapi`, and `uvicorn` couldn't be installed to run the real pipeline
end-to-end. Instead I:

- Syntax-checked every Python file (`py_compile`) and every JS file (`node --check`).
- Ran `voice_pipeline.run_screening()` against a mocked `librosa`/`parselmouth`
  (synthetic sine-wave audio, deterministic fake Praat calls) to verify the
  full control flow — quality gate, feature assembly, imputation, scaling,
  prediction, and JSON shape — for both the success path and the
  too-quiet/too-short rejection path. Both returned the exact structure the
  frontend expects.
- Validated all five HTML pages for balanced tags and required structure.

**Before you rely on this:** run it locally with your real dependencies and a
real recording, and check the browser console + `uvicorn` logs for anything
this sandbox couldn't surface (e.g. actual mic/codec quirks across browsers).

## Pages

| Page | File | Notes |
|---|---|---|
| Home | `frontend/index.html` | Landing page, disclaimer, how-it-works |
| Screening | `frontend/screening.html` | Record/upload → analyze → results, all client-side state |
| History | `frontend/history.html` | Real session history from `/api/history` (not mock data) — empty until you run screenings |
| About | `frontend/about.html` | Methodology, features used, limitations, privacy |
| Settings | `frontend/settings.html` | Microphone selection, light/dark theme (saved in `localStorage` only) |

## Design notes

Palette is a cool off-white background with a deep teal accent (`#0E6E63`)
for primary actions and a muted brick tone (`#7A3B31`) reserved for elevated
findings — deliberately not clinical-teal-on-white-with-gradients or a
generic SaaS look. Type is IBM Plex Sans for reading, IBM Plex Mono for every
actual data readout (IDs, timestamps, probabilities, feature values) so
numbers are visually distinct from prose. All tokens are CSS variables in
`frontend/css/style.css:root` — including a `[data-theme="dark"]` override
block — if you want to adjust the palette.

## Comparing a patient's progress over time

Screening now accepts an optional **Patient ID** field. Screenings submitted
with the same Patient ID are grouped together, and the new **Compare** page
(`compare.html`) shows:

- a probability trend chart across all of that patient's screenings
- a side-by-side comparison of any two screenings (earlier vs. later)
- a feature-by-feature delta table (jitter, shimmer, HNR, F0 mean/variability)

New endpoints backing this: `GET /api/patients` (distinct patients + counts),
`GET /api/patients/{id}/screenings` (that patient's completed screenings,
oldest first). Like the rest of history, this is in-memory per server session
— see "Known gaps" below.

## Hosting this online

Two ready-made paths are included:

**Replit** — `.replit` and `run_replit.sh` are already set up. See the
step-by-step walkthrough your assistant gave you, or in short: import this
folder as a Python repl, click Run once to install dependencies, then Run
again (or use Replit Deployments for a stable URL).

**Docker (Render / Railway / Fly.io / any VPS)** — `Dockerfile` builds a
single container serving both the API and the frontend. Push to a registry
or connect your repo to the platform of choice; it auto-detects the
Dockerfile. Set no environment variables required by default.

**Before hosting with real patient data:** this prototype has no
authentication, stores history/patient records only in server memory (wiped
on restart), and sends audio over plain HTTP unless your host provides TLS.
None of that is appropriate for real, identifiable patient recordings without
further work — treat Patient ID as a coded/anonymized identifier, not a name,
until you've added proper auth, encrypted storage, and consent handling.

## Known gaps / next steps- History and screenings are in-memory on the backend only — restart the
  server and they're gone. Swap `_history` in `main.py` for SQLite or a real
  store if you need persistence.
- Mic recordings are captured as `audio/webm` (browser default); `librosa.load`
  handles this fine via `soundfile`/`audioread`, but confirm this on your
  actual machine — some minimal environments lack the audioread backend for
  webm and may need `ffmpeg` installed.
- No authentication — this is a local research prototype, not deployed
  anywhere multi-tenant.
