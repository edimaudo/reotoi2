"""Voice-to-art pipeline with explicit engine provenance and labelled fallbacks."""
from __future__ import annotations
import base64
import logging
import math
import uuid
from urllib.parse import unquote
from services import meta_ai
from services.art_generator import build_visual_parameters, choose_theme, render_svg

logger = logging.getLogger("reotoi.pipeline")
OUTPUT_MODES = {"svg", "muse_image", "fusion"}
ART_STYLES = {"painterly", "ink_wash", "cut_paper", "luminous_surrealism", "generative_linework", "surprise"}


def _local_brief(dna: dict, theme: str, style: str) -> dict:
    pitch, energy, rhythm, variation, pause = (dna.get(k, 5) for k in ("pitch", "energy", "rhythm", "variation", "pause"))
    colors = "deep indigo, charcoal and burnt amber" if pitch < 4 else "teal, sand and soft coral" if pitch < 7 else "pale gold, sky blue and white"
    style_names = {
        "painterly": "expressive painting with visible brush gestures and layered pigment",
        "ink_wash": "fluid ink contours with translucent washes and paper texture",
        "cut_paper": "layered cut-paper shapes with tactile edges and dimensional overlap",
        "luminous_surrealism": "luminous surreal forms, unusual scale and dreamlike light",
        "generative_linework": "intricate repeated linework and fine flowing patterns",
        "surprise": "a distinctive visual technique chosen to suit the voice",
    }
    prompt = (f"A {theme} composition in {colors}, made as {style_names.get(style, style_names['surprise'])}. "
              f"Use {'dense layers' if energy > 6 else 'balanced spacing' if energy > 3 else 'sparse elements'}, "
              f"{'repeated quick marks' if rhythm > 6 else 'slow flowing shapes'}, "
              f"{'strong contrast' if variation > 6 else 'gentle contrast'}, and "
              f"{'generous negative space' if pause > 6 else 'connected forms'}. No text or lettering.")
    return {"title": f"{theme.title()} Voice Study", "mood": "creative study", "sentiment": 0.0, "prompt": prompt}


def _compose_fusion(image_uri: str, features: dict, artwork_id: str) -> str:
    """Place a voice-driven vector overlay above an AI-generated raster image."""
    pitch = float(features.get("pitch", 0.5))
    energy = float(features.get("energy", 0.5))
    rhythm = float(features.get("rhythm", 0.5))
    variation = float(features.get("variation", 0.5))
    pause = float(features.get("pause", 0.3))
    accent = "#f0c987" if pitch < .45 else "#8de0d0" if pitch < .7 else "#d4c6ff"
    secondary = "#ffffff" if variation > .45 else "#26364d"
    amp = 12 + energy * 32
    cycles = 2.2 + rhythm * 6
    points = []
    for i in range(121):
        x = 40 + (720 * i / 120)
        y = 400 + math.sin((i / 120) * math.tau * cycles) * amp + math.sin((i / 120) * math.pi * 2) * (pause * 12)
        points.append(f"{x:.1f},{y:.1f}")
    path = "M " + " L ".join(points)
    # Voice-linked graphic annotations remain legible and intentionally transparent.
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800" role="img">'
           f'<title>reotoi Fusion artwork</title><desc>AI-generated artwork with a transparent vector overlay shaped by measured voice characteristics.</desc>'
           f'<image href="{image_uri}" x="0" y="0" width="800" height="800" preserveAspectRatio="xMidYMid slice"/>'
           f'<path d="{path}" fill="none" stroke="{accent}" stroke-width="{1.8 + variation*2.0:.1f}" opacity="0.8"/>'
           f'<circle cx="400" cy="400" r="{65 + energy*85:.1f}" fill="none" stroke="{secondary}" stroke-width="1.5" opacity="0.42"/>'
           f'<circle cx="400" cy="400" r="{98 + rhythm*95:.1f}" fill="none" stroke="{accent}" stroke-width="1.2" stroke-dasharray="{2 + rhythm*7:.1f} 12" opacity="0.64"/>'
           f'<path d="M 75 95 L 120 95 M 75 95 L 75 140 M 725 95 L 680 95 M 725 95 L 725 140 M 75 705 L 120 705 M 75 705 L 75 660 M 725 705 L 680 705 M 725 705 L 725 660" stroke="{accent}" stroke-width="2" fill="none" opacity="0.8"/>'
           f'</svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


async def create_artwork(*, features: dict, voice_dna: dict, theme: str, art_style: str, output_mode: str, audio_path: str) -> dict:
    """Create vector art, an AI-generated image, or Fusion with a vector overlay."""
    if output_mode not in OUTPUT_MODES:
        raise ValueError("Invalid output mode.")
    if art_style not in ART_STYLES:
        raise ValueError("Invalid art style.")
    resolved_theme = choose_theme(theme)
    configured = meta_ai.is_configured()
    transcript = None
    brief = _local_brief(voice_dna, resolved_theme, art_style)
    engine = {"transcription": "Not used", "prompt": "Local prompt", "image": "Not used"}
    notes = []

    # The SVG-only mode never makes a paid image-generation request.
    if output_mode in {"muse_image", "fusion"} and configured:
        try:
            transcript = await meta_ai.transcribe(audio_path) or None
            engine["transcription"] = meta_ai.VOICE_MODEL
        except meta_ai.MetaAIError as exc:
            engine["transcription"] = "Unavailable"
            logger.warning("Voice transcription unavailable: %s", exc)
        try:
            brief = await meta_ai.write_art_brief(voice_dna, features.get("duration", 0.0), resolved_theme, transcript, art_style)
            engine["prompt"] = meta_ai.SPARK_MODEL
        except meta_ai.MetaAIError as exc:
            engine["prompt"] = "Local prompt (prompt generation unavailable)"
            logger.warning("Prompt generation unavailable: %s", exc)

    image_uri = None
    if output_mode in {"muse_image", "fusion"} and configured:
        try:
            image_uri = await meta_ai.render_image(brief["prompt"])
            engine["image"] = meta_ai.IMAGE_MODEL
        except meta_ai.MetaAIError as exc:
            logger.warning("AI image generation unavailable: %s", exc)
            notes.append("AI image generation was unavailable; locally rendered vector artwork was used instead.")
    elif output_mode in {"muse_image", "fusion"}:
        notes.append("AI image generation is not configured; locally rendered vector artwork was used instead.")

    if output_mode == "svg":
        artwork_id, artwork_url, parameters = render_svg(features, resolved_theme)
        actual_mode = "svg"
        artwork_engine = "Local vector renderer"
        notes.append("This is vector artwork rendered locally from voice-driven shapes and lines. It may not reproduce every nuance of the selected technique.")
    elif image_uri and output_mode == "muse_image":
        artwork_id = str(uuid.uuid4())
        artwork_url = image_uri
        parameters = build_visual_parameters(features, resolved_theme)
        actual_mode = "muse_image"
        artwork_engine = "AI image generator"
        notes.append("An AI-generated image was created using the selected theme, art style and available voice information.")
    elif image_uri and output_mode == "fusion":
        artwork_id = str(uuid.uuid4())
        artwork_url = _compose_fusion(image_uri, features, artwork_id)
        parameters = build_visual_parameters(features, resolved_theme)
        actual_mode = "fusion"
        artwork_engine = "Fusion (AI image + vector overlay)"
        notes.append("Fusion combines an AI-generated image with a transparent, voice-driven vector overlay.")
    else:
        artwork_id, artwork_url, parameters = render_svg(features, resolved_theme)
        actual_mode = "svg_fallback"
        artwork_engine = "Local vector renderer"
        notes.append("The requested AI output was unavailable. This is vector-art fallback, not an AI image or Fusion output.")

    return {
        "artwork_id": artwork_id,
        "artwork_url": artwork_url,
        "theme": resolved_theme,
        "art_style": art_style,
        "output_mode_requested": output_mode,
        "output_mode_used": actual_mode,
        "artwork_engine": artwork_engine,
        "source_note": " ".join(notes),
        "visual_parameters": parameters,
        "title": brief.get("title") or f"{resolved_theme.title()} Voice Study",
        "mood": brief.get("mood") or "creative study",
        "prompt": brief.get("prompt", ""),
        "transcript": transcript,
        "engine": engine,
        "meta_ai": configured,
        "fusion": actual_mode == "fusion",
    }
