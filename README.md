# reotoi · voice art

reotoi turns a short voice recording into original artwork. It is a server-rendered FastAPI application with vanilla JavaScript, HTML and CSS for the browser UI.

## Art direction setup

The creation page uses a three-step flow: visual theme, art style, and output mode. Each theme and technique includes a short description, and the selected direction is summarized before the user records audio. Themes describe the visual world; art styles describe the technique and texture.

## Output modes

- **Vector art** — uses the local procedural renderer; no image-generation call is made.
- **AI image** — requests a generated raster image when the image API is configured.
- **Fusion** — combines generated image output with a transparent, voice-driven vector overlay.

If an AI image request cannot run, the application produces a local SVG fallback and labels the actual renderer in the result. It never labels a fallback as an AI image or Fusion.

## Voice DNA

The local analysis reports normalized pitch, energy, rhythm, variation and pause estimates. The values are visual inputs, not a clinical emotion assessment. Onset strength is used only as a rhythm proxy; it is **not** described as speech rate because the application does not compute words per minute.

## Run locally

Use Python 3.11 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
# Set SESSION_SECRET and the demo credentials in .env before deployment.
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. The login screen pre-fills the configured demo username and password. If `DEMO_USERNAME` and `DEMO_PASSWORD` are not set in the environment, the built-in defaults are `demo` / `reotoi-demo`; the `.env.example` file provides a replacement password to encourage local configuration. This is prototype authentication, not a production identity system. Use a strong random `SESSION_SECRET`; the built-in `dev-only-change-me` session signing fallback is only for local development. Set `SESSION_HTTPS_ONLY=1` behind HTTPS.

## Meta Model API settings

Set `MODEL_API_KEY` (or `META_API_KEY`) to enable voice transcription, prompt generation, and AI image generation. `META_API_BASE` defaults to `https://api.meta.ai/v1`. Model IDs and timeouts can be overridden in the environment; see `.env.example`. Image and transcription calls are made only for AI image and Fusion modes. The SVG-only mode is local. The current tests exercise input validation, Fusion composition and truthful fallback labels. They do not validate live credentials, API availability, or image quality.

## Gallery and persistence

Saved artwork is stored in the browser's `localStorage` under `reotoi-gallery`. It is local to that browser and device; it is not a server-side account gallery and will not automatically sync across devices. Clearing browser site data can remove saved pieces.

## Accessibility

The interface uses Inter, keyboard-visible focus styles, a skip link, screen-reader labels and descriptions, responsive layouts, light/dark themes and Small/Medium/Large text-size controls. Theme and text-size preferences persist in browser `localStorage`. These features are not a formal WCAG conformance certification; perform a keyboard, screen-reader, contrast and zoom/reflow audit before making a compliance claim.

## Deployment and security notes

`vercel.json` uses Vercel's Python runtime for `main.py`. Configure all secrets in the deployment environment rather than committing `.env`. The demo username/password and cookie signing secret are configuration defaults for a prototype; do not use them for real accounts. The local upload is size- and duration-limited, normalized to WAV before analysis, and removed from the temporary directory after processing. Logs should not include raw audio or API keys.


For the demo account header, set `DEMO_DISPLAY_NAME` (defaults to `James`). This is a display name only; the demo login username remains configured through `DEMO_USERNAME`.
