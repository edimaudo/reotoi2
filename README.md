# reotoi | Voice Art

Turn your voice into visual art.

*The name **reotoi** comes from the Māori language: reo (voice) and toi (art).*

## How it works

```
microphone / audio file
        │  (browser converts to mono 16 kHz PCM WAV)
        ▼
 librosa voice analysis ──► Voice DNA (pitch, energy, rhythm, variation, pause)
        │
        ├─► Muse Voice Transcribe  ──► transcript
        ├─► Muse Spark             ──► title, mood and an image prompt
        └─► Muse Image             ──► the artwork
                 │
                 └─ if any Meta call fails, reotoi falls back (see below)
```

| Step | Model | Endpoint |
|------|-------|----------|
| Transcribe | `muse-voice-transcribe-1.0` | `POST /v1/asr/transcribe` |
| Write the prompt | `muse-spark-1.3` (Standard mode) | `POST /v1/chat/completions` |
| Render | `muse-image-1.0` | `POST /v1/images/generations` |

Base URL `https://api.meta.ai/v1`, bearer auth. Get a key at https://dev.meta.ai.

**Fallbacks.** No key, or a failed call, never breaks the app:
transcription is skipped, a feature-driven local prompt replaces Muse Spark, and
the original procedural SVG renderer (`services/art_generator.py`) replaces Muse Image.
The result card shows which engine produced each step.

**Privacy.** The transcript and Voice DNA are sent to Meta. Muse Spark runs in Standard
mode, where Meta says content is not used for training. Audio is only sent to Muse Voice
Transcribe. Check Meta's geographic availability policy for your region.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add MODEL_API_KEY, set SESSION_SECRET
python main.py              # http://127.0.0.1:8000
```

### Demo login

| Username | Password |
|----------|----------|
| `demo` | `reotoi-demo` |

Override with `DEMO_USERNAME` / `DEMO_PASSWORD`, and hide the hint on the login page with
`SHOW_DEMO_CREDENTIALS=0`. This is a single demo account for trying the app; replace
`services/auth.py` with a real user store before accepting real users.

### Tests

```bash
pip install -r requirements-dev.txt
pytest
```

Tests mock the Meta API, covering login, the full pipeline and each fallback path.

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `MODEL_API_KEY` | Meta Model API key | none (local mode) |
| `META_SPARK_MODEL` | Prompt model | `muse-spark-1.3` |
| `META_IMAGE_MODEL` | Image model | `muse-image-1.0` |
| `META_VOICE_MODEL` | Transcription model | `muse-voice-transcribe-1.0` |
| `SESSION_SECRET` | Cookie signing key | dev value, change it |
| `SESSION_HTTPS_ONLY` | Secure cookies | off |

## Project structure

```
reotoi/
├── main.py                  routes, sessions, /login, /generate
├── requirements.txt
├── requirements-dev.txt
├── .env.example
├── vercel.json
├── services/
│   ├── auth.py              demo account and safe redirects
│   ├── meta_ai.py           Muse Voice Transcribe, Muse Spark, Muse Image
│   ├── pipeline.py          Meta first, local fallbacks
│   ├── voice_features.py    librosa analysis
│   ├── art_generator.py     procedural SVG fallback
│   ├── audio_conversion.py
│   └── gallery_service.py
├── templates/               base, index, login, app, gallery, 404, 500
├── static/                  css and js
└── tests/test_app.py
```
