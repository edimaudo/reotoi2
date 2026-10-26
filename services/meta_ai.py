"""Meta Model API client for reotoi.

The supported workflow is Muse Voice Transcribe -> Muse Spark -> Muse Image.
Every call raises MetaAIError on failure so the pipeline can produce and label
an honest local SVG fallback. API keys are only read from environment variables.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
import httpx

logger = logging.getLogger("reotoi.meta")
API_BASE = os.getenv("META_API_BASE", "https://api.meta.ai/v1").rstrip("/") + "/"
SPARK_MODEL = os.getenv("META_SPARK_MODEL", "muse-spark-1.3")
IMAGE_MODEL = os.getenv("META_IMAGE_MODEL", "muse-image-1.0")
VOICE_MODEL = os.getenv("META_VOICE_MODEL", "muse-voice-transcribe-1.0")
TEXT_TIMEOUT = float(os.getenv("META_TIMEOUT_SECONDS", "45"))
IMAGE_TIMEOUT = float(os.getenv("META_IMAGE_TIMEOUT_SECONDS", "120"))
_TRANSPORT: httpx.AsyncBaseTransport | None = None  # injectable in tests

class MetaAIError(RuntimeError):
    """A Meta Model API request failed or returned an unusable response."""

def api_key() -> str | None:
    return os.getenv("MODEL_API_KEY") or os.getenv("META_API_KEY") or None

def is_configured() -> bool:
    return bool(api_key())

def _client(timeout: float) -> httpx.AsyncClient:
    key = api_key()
    if not key:
        raise MetaAIError("MODEL_API_KEY is not set.")
    return httpx.AsyncClient(
        base_url=API_BASE,
        timeout=timeout,
        headers={"Authorization": f"Bearer {key}"},
        transport=_TRANSPORT,
    )

def _check(response: httpx.Response, what: str) -> dict:
    if response.status_code >= 400:
        raise MetaAIError(f"{what} failed with HTTP {response.status_code}: {response.text[:200]}")
    try:
        body = response.json()
    except ValueError as exc:
        raise MetaAIError(f"{what} returned a non-JSON response.") from exc
    if not isinstance(body, dict):
        raise MetaAIError(f"{what} returned an unexpected response shape.")
    return body

async def transcribe(wav_path: str | Path) -> str:
    """Transcribe prepared mono PCM WAV audio with Muse Voice Transcribe."""
    audio = Path(wav_path).read_bytes()
    try:
        async with _client(TEXT_TIMEOUT) as client:
            response = await client.post(
                "asr/transcribe",
                files={"file": ("recording.wav", audio, "audio/wav")},
                data={"model": VOICE_MODEL},
            )
    except httpx.HTTPError as exc:
        raise MetaAIError(f"Transcription request failed: {exc.__class__.__name__}") from exc
    body = _check(response, "Transcription")
    text = body.get("text") or body.get("transcript") or ""
    if isinstance(text, list):
        text = " ".join(str(part) for part in text)
    return str(text).strip()

SPARK_SYSTEM = (
    "You are the art director for reotoi, an app that turns voice characteristics into original artwork. "
    "You receive measured voice features on 0–10 scales, a semantic theme, a visual art style, and optionally a transcript. "
    "Write one 60–90 word prompt for an image model describing subject, composition, named colours, texture and light. "
    "Respect the style as a distinct visual treatment: painterly, ink wash, cut-paper collage, luminous surrealism, "
    "intricate generative linework, or a considered surprise choice. Pitch influences palette temperature; energy influences density; "
    "rhythm influences mark repetition; variation influences contrast; pauses influence negative space. Stay true to the theme, "
    "do not illustrate or quote transcript words literally, and include no text, lettering, logos or real people. "
    "Return only JSON with keys title (2–4 words), mood (one word, creative interpretation only), sentiment (-1 to 1), and prompt (string)."
)

def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise MetaAIError("Muse Spark did not return JSON.")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise MetaAIError("Muse Spark returned malformed JSON.") from exc
    if not isinstance(data, dict):
        raise MetaAIError("Muse Spark returned an unexpected JSON shape.")
    return data

async def write_art_brief(
    voice_dna: dict, duration: float, theme: str, transcript: str | None,
    art_style: str = "painterly",
) -> dict:
    """Use Muse Spark to shape an art prompt from voice metrics, theme and style."""
    user = json.dumps({
        "theme": theme,
        "art_style": art_style,
        "voice_features_0_to_10": voice_dna,
        "duration_seconds": round(duration, 1),
        "transcript": transcript or None,
    })
    payload = {
        "model": SPARK_MODEL,
        "messages": [
            {"role": "system", "content": SPARK_SYSTEM},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.8,
        "max_tokens": 700,
    }
    try:
        async with _client(TEXT_TIMEOUT) as client:
            response = await client.post("chat/completions", json=payload)
    except httpx.HTTPError as exc:
        raise MetaAIError(f"Muse Spark request failed: {exc.__class__.__name__}") from exc
    body = _check(response, "Muse Spark")
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MetaAIError("Muse Spark response had no message content.") from exc
    brief = _extract_json(str(content))
    prompt = str(brief.get("prompt", "")).strip()
    if len(prompt) < 30:
        raise MetaAIError("Muse Spark returned an empty prompt.")
    try:
        sentiment = max(-1.0, min(1.0, float(brief.get("sentiment", 0))))
    except (TypeError, ValueError):
        sentiment = 0.0
    return {
        "title": str(brief.get("title") or "").strip()[:60] or None,
        "mood": str(brief.get("mood") or "").strip().lower()[:24] or None,
        "sentiment": sentiment,
        "prompt": prompt[:1500],
    }

def _mime_for(raw: bytes) -> str:
    if raw[:8] == b"\x89PNG\r\n\x1a\n": return "image/png"
    if raw[:3] == b"\xff\xd8\xff": return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP": return "image/webp"
    raise MetaAIError("Muse Image returned an unrecognized image format.")

async def render_image(prompt: str) -> str:
    """Generate one image with Muse Image and return a validated data URI."""
    payload = {"model": IMAGE_MODEL, "prompt": prompt, "size": "1024x1024", "response_format": "b64_json"}
    try:
        async with _client(IMAGE_TIMEOUT) as client:
            response = await client.post("images/generations", json=payload)
    except httpx.HTTPError as exc:
        raise MetaAIError(f"Muse Image request failed: {exc.__class__.__name__}") from exc
    body = _check(response, "Muse Image")
    try:
        encoded = body["data"][0]["b64_json"]
        raw = base64.b64decode(encoded, validate=False)
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise MetaAIError("Muse Image response had no image data.") from exc
    if len(raw) < 64:
        raise MetaAIError("Muse Image returned an empty image.")
    return f"data:{_mime_for(raw)};base64,{base64.b64encode(raw).decode('ascii')}"
