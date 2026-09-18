# Parkinson Voice Screening — run and host

A research prototype. Not a medical device, not clinically validated, not for any
diagnostic or care decision.

## Layout

```
.
├── main.py                     FastAPI: /api/health, /api/analyze, serves frontend at /
├── requirements.txt
├── Dockerfile
├── model/
│   ├── model.joblib            your trained classifier
│   ├── scaler.joblib           the scaler fitted on the training split
│   └── model_meta.json         copy of model_meta.example.json, edited
└── frontend/
    ├── index.html  screen.html  history.html  about.html  settings.html
    ├── styles.css  api.js  app.js  history.js  settings.js  shell.js  store.js  theme.js
```

Put every file where this tree shows. `main.py` mounts `frontend/` at `/`, so the
page and the API share an origin and `API_BASE` in `api.js` stays empty.

## Before anything else: feature order

`main.py` measures 12 features and feeds them to the model **in the order listed in
`model/model_meta.json`**. If that order doesn't match the column order used at
training time, the model will return confident nonsense — no error, just wrong
numbers. Copy `model_meta.example.json` to `model/model_meta.json` and edit the
`features` array to match your training columns exactly.

If your training columns came from the UCI Parkinsons CSV (MDVP:Fo, MDVP:Jitter(%),
etc.) rather than from Praat measurements of raw audio, the names and the scales
are different and you have to map them. Check `GET /api/health` — it echoes the
order the server will use.

## 1. Run it on your machine

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open <http://localhost:8000>.

You also need **ffmpeg** on your PATH, because Chrome and Firefox record WebM/Opus,
not WAV:

- macOS: `brew install ffmpeg`
- Ubuntu/Debian: `sudo apt install ffmpeg`
- Windows: `winget install Gyan.FFmpeg`, then reopen the terminal

Check it worked: <http://localhost:8000/api/health> should show
`"model_loaded": true` and `"ffmpeg": true`.

If `scikit-learn` complains about a version mismatch when loading the model, change
the pinned version in `requirements.txt` to the version you trained with, or
re-fit and re-save the model with 1.5.2.

## 2. Host it publicly

The microphone only works on `https://` or `localhost`. Any host below gives you
HTTPS automatically. A static host (GitHub Pages, Netlify) can't run this alone —
the model inference is Python.

### Hugging Face Spaces — free, easiest, no card

1. Create an account at <https://huggingface.co>.
2. **New Space** → name it → **Docker** → **Blank** → Public or Private → Create.
3. Clone it and push your files:

```bash
git clone https://huggingface.co/spaces/<your-username>/<space-name>
cd <space-name>
# copy main.py, requirements.txt, Dockerfile, frontend/, model/ in here
git add -A
git commit -m "Parkinson voice screening prototype"
git push
```

If `model.joblib` is over 10 MB, run `git lfs install && git lfs track "*.joblib"`
and commit `.gitattributes` before pushing.

The Space builds and serves on port 7860, which the Dockerfile already sets. Watch
the build log on the Space page; first build takes a few minutes.

### Render — free tier, sleeps when idle

1. Push the project to a GitHub repo.
2. <https://render.com> → **New** → **Web Service** → connect the repo.
3. Runtime **Docker**, leave build and start commands blank (the Dockerfile handles
   both), instance type **Free** → Create.

Render injects `PORT`; the Dockerfile's start command already reads it. Free
instances spin down after inactivity, so the first request after a pause takes
around a minute.

### Fly.io — always-on, needs a card on file

```bash
fly launch --no-deploy      # accept the detected Dockerfile, skip databases
fly deploy
```

Then set `internal_port = 7860` in the generated `fly.toml` if launch guessed
something else.

## 3. After deploying, check these four things

1. `https://your-url/api/health` → `model_loaded: true`, `ffmpeg: true`.
2. The landing page loads and the sidebar status dot on `/screen.html` is green.
3. Record a 5-second "ahh" in Chrome and confirm you get a probability back, not a
   415 or 422.
4. Open it on a phone — the mic prompt only appears over HTTPS, so this is the test
   that catches a broken deploy.

## Before you share the link with anyone

- Keep every disclaimer in place. The result is a similarity score against a small
  training set, and people will read it as a health verdict unless the page says
  otherwise on every screen.
- Fill in the `—` placeholders on the model card with metrics from a
  **speaker-disjoint** test split. Splitting by clip inflates every number, because
  recordings from the same person land on both sides.
- If you put it in front of anyone besides yourself, say plainly that audio is sent
  to your server for processing, and check what your institution requires before
  collecting voice recordings from other people.
