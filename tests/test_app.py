from __future__ import annotations
import base64
import pytest
from fastapi import HTTPException
import main
from services import pipeline


def test_valid_selection_values():
    assert main.validate_theme("COSMOS") == "cosmos"
    assert main.validate_art_style("ink_wash") == "ink_wash"
    assert main.validate_output_mode("fusion") == "fusion"
    assert main.validate_input_source("upload") == "upload"

@pytest.mark.parametrize("validator,value", [
    (main.validate_theme, "not-a-theme"),
    (main.validate_art_style, "not-a-style"),
    (main.validate_output_mode, "unknown-mode"),
    (main.validate_input_source, "url"),
])
def test_invalid_selection_is_rejected(validator, value):
    with pytest.raises(HTTPException) as error:
        validator(value)
    assert error.value.status_code == 422


def test_fusion_wrapper_contains_raster_and_vector_overlay():
    raster = "data:image/png;base64," + base64.b64encode(b"fake-png-payload" * 10).decode()
    uri = pipeline._compose_fusion(raster, {"pitch": .5, "energy": .8, "rhythm": .4, "variation": .7, "pause": .2}, "test-id")
    assert uri.startswith("data:image/svg+xml;base64,")
    document = base64.b64decode(uri.split(",", 1)[1]).decode()
    assert '<image href="data:image/png;base64,' in document
    assert '<path d="M ' in document
    assert "Fusion artwork" in document


def test_svg_mode_is_explicit_local_renderer(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.meta_ai, "is_configured", lambda: False)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"not used in svg mode")
    result = __import__("asyncio").run(pipeline.create_artwork(
        features={"pitch": .5, "energy": .5, "rhythm": .5, "variation": .4, "pause": .2, "duration": 1.0},
        voice_dna={"pitch": 5, "energy": 5, "rhythm": 5, "variation": 4, "pause": 2},
        theme="cosmos", art_style="painterly", output_mode="svg", audio_path=str(audio_path),
    ))
    assert result["output_mode_used"] == "svg"
    assert result["artwork_engine"] == "Local SVG renderer"
    assert result["artwork_url"].startswith("data:image/svg+xml")
    assert result["fusion"] is False


def test_requested_ai_mode_without_key_is_not_mislabeled(monkeypatch, tmp_path):
    monkeypatch.setattr(pipeline.meta_ai, "is_configured", lambda: False)
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"not used in pipeline fallback")
    result = __import__("asyncio").run(pipeline.create_artwork(
        features={"pitch": .5, "energy": .5, "rhythm": .5, "variation": .4, "pause": .2, "duration": 1.0},
        voice_dna={"pitch": 5, "energy": 5, "rhythm": 5, "variation": 4, "pause": 2},
        theme="cosmos", art_style="ink_wash", output_mode="fusion", audio_path=str(audio_path),
    ))
    assert result["output_mode_used"] == "svg_fallback"
    assert result["artwork_engine"] == "Local SVG renderer"
    assert result["fusion"] is False
    assert "not Muse Image or Fusion" in result["source_note"]
