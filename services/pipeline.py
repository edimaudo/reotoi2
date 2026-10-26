"""Voice-to-art pipeline: Meta AI first, reotoi's own renderer as the safety net."""

from __future__ import annotations

import logging
import re
import uuid

from services import meta_ai
from services.art_generator import build_visual_parameters, choose_theme, render_svg

logger = logging.getLogger("reotoi.pipeline")

LOCAL = "reotoi local renderer"
POSITIVE = set("love loved happy great good wonderful amazing excited joy beautiful grateful calm peaceful hope proud fun enjoy bright smile warm lucky thank".split())
NEGATIVE = set("sad angry hate bad terrible awful tired worried afraid anxious stress lonely hurt dark broken lost fear cry pain empty sorry tense".split())


def _sentiment(text: str | None) -> float:
    words = re.findall(r"[a-z']+", (text or "").lower())
    pos, neg = sum(w in POSITIVE for w in words), sum(w in NEGATIVE for w in words)
    return (pos - neg) / (pos + neg) if pos + neg else 0.0


def _mood(dna: dict, sentiment: float) -> str:
    arousal = (dna.get("energy", 5) + dna.get("rhythm", 5)) / 20
    if sentiment > 0.2:
        return "joyful" if arousal > 0.5 else "warm"
    if sentiment < -0.2:
        return "tense" if arousal > 0.5 else "somber"
    return "driven" if arousal > 0.6 else "quiet" if arousal < 0.3 else "steady"


def local_brief(dna: dict, theme: str, transcript: str | None) -> dict:
    """Specific, feature-driven fallback used when Muse Spark is unavailable."""
    pitch, energy, rhythm, variation, pause = (dna.get(k, 5) for k in ("pitch", "energy", "rhythm", "variation", "pause"))
    sentiment = _sentiment(transcript)
    mood = _mood(dna, sentiment)
    colors = "deep indigo, charcoal and burnt amber" if pitch < 4 else "teal, sand and soft coral" if pitch < 7 else "pale gold, sky blue and white"
    prompt = (
        f"A {theme} composition in {colors}, {'densely layered' if energy > 6 else 'moderately filled' if energy > 3 else 'sparse'} "
        f"with {'quick, repeated marks' if rhythm > 6 else 'slow sweeping forms'}, {'high contrast' if variation > 6 else 'gentle contrast'}, "
        f"{'wide open negative space' if pause > 6 else 'little empty space'}, a {mood} mood, soft directional light, "
        "painterly texture, no text or letters."
    )
    return {"title": f"{mood.capitalize()} {theme}", "mood": mood, "sentiment": sentiment, "prompt": prompt}


async def create_artwork(*, features: dict, voice_dna: dict, theme: str, audio_path: str) -> dict:
    resolved = choose_theme(theme)
    engine = {"transcription": LOCAL + " (not run)", "prompt": LOCAL, "image": LOCAL}
    transcript = None

    if meta_ai.is_configured():
        try:
            transcript = await meta_ai.transcribe(audio_path) or None
            engine["transcription"] = meta_ai.VOICE_MODEL
        except meta_ai.MetaAIError as exc:
            logger.warning("Muse Voice Transcribe unavailable: %s", exc)
            engine["transcription"] = "unavailable"

    brief = None
    if meta_ai.is_configured():
        try:
            brief = await meta_ai.write_art_brief(voice_dna, features.get("duration", 0.0), resolved, transcript)
            engine["prompt"] = meta_ai.SPARK_MODEL
        except meta_ai.MetaAIError as exc:
            logger.warning("Muse Spark unavailable: %s", exc)
    if brief is None:
        brief = local_brief(voice_dna, resolved, transcript)
    brief["mood"] = brief.get("mood") or _mood(voice_dna, brief.get("sentiment", 0.0))
    brief["title"] = brief.get("title") or f"{brief['mood'].capitalize()} {resolved}"

    artwork_url = None
    if meta_ai.is_configured():
        try:
            artwork_url = await meta_ai.render_image(brief["prompt"])
            engine["image"] = meta_ai.IMAGE_MODEL
        except meta_ai.MetaAIError as exc:
            logger.warning("Muse Image unavailable: %s", exc)

    if artwork_url:
        artwork_id = str(uuid.uuid4())
        parameters = build_visual_parameters(features, resolved)
    else:
        artwork_id, artwork_url, parameters = render_svg(features, resolved)

    return {
        "artwork_id": artwork_id,
        "artwork_url": artwork_url,
        "theme": resolved,
        "visual_parameters": parameters,
        "title": brief["title"],
        "mood": brief["mood"],
        "prompt": brief["prompt"],
        "transcript": transcript,
        "engine": engine,
        "meta_ai": meta_ai.is_configured(),
    }
