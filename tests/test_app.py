"""End-to-end tests with a mocked Meta Model API (no network, no real key)."""

import base64
import io
import json

import httpx
import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

import main
from services import meta_ai

# Smallest valid PNG (1x1), padded so it passes the "not empty" size check.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
PNG = PNG + b"\x00" * 64


def wav_bytes(seconds=3.0, sr=16000):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    voice = 0.3 * np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 3 * t))
    buf = io.BytesIO()
    sf.write(buf, voice.astype("float32"), sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def meta_handler(fail=()):
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        calls.append(path)
        assert request.headers["authorization"] == "Bearer test-key"
        step = path.rsplit("/", 1)[-1]
        if step in fail:
            return httpx.Response(500, json={"error": "boom"})
        if path.endswith("/asr/transcribe"):
            return httpx.Response(200, json={"text": "I love the sound of rain tonight"})
        if path.endswith("/chat/completions"):
            brief = {
                "title": "Rain Tonight",
                "mood": "warm",
                "sentiment": 0.8,
                "prompt": "A cosmos composition of deep indigo and amber light, layered rings drifting through wide negative space, soft grain, calm mood, no text.",
            }
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(brief)}}]})
        if path.endswith("/images/generations"):
            return httpx.Response(200, json={"data": [{"b64_json": base64.b64encode(PNG).decode()}]})
        return httpx.Response(404)

    return handler, calls


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    return TestClient(main.app, follow_redirects=False)


def login(client):
    return client.post("/login", data={"username": "demo", "password": "reotoi-demo", "next": "/create"})


def generate(client, theme="cosmos"):
    return client.post(
        "/generate",
        files={"audio": ("rec.wav", wav_bytes(), "audio/wav")},
        data={"theme": theme, "input_source": "microphone"},
    )


def test_pages_require_login(client):
    for path in ("/create", "/gallery"):
        r = client.get(path)
        assert r.status_code == 303 and r.headers["location"].startswith("/login?next=")
    assert generate(client).status_code == 401


def test_login_page_shows_demo_credentials_and_rejects_bad_password(client):
    page = client.get("/login")
    assert page.status_code == 200 and "reotoi-demo" in page.text and "demo" in page.text
    bad = client.post("/login", data={"username": "demo", "password": "nope"})
    assert bad.status_code == 401 and "not correct" in bad.text


def test_login_logout_and_open_redirect_guard(client):
    r = client.post("/login", data={"username": "demo", "password": "reotoi-demo", "next": "//evil.example"})
    assert r.status_code == 303 and r.headers["location"] == "/create"
    assert client.get("/create").status_code == 200
    assert client.post("/logout").status_code == 303
    assert client.get("/create").status_code == 303


def test_full_meta_pipeline(client):
    handler, calls = meta_handler()
    meta_ai._TRANSPORT = httpx.MockTransport(handler)
    try:
        login(client)
        body = generate(client).json()
    finally:
        meta_ai._TRANSPORT = None
    assert calls == ["/v1/asr/transcribe", "/v1/chat/completions", "/v1/images/generations"]
    assert body["transcript"] == "I love the sound of rain tonight"
    assert body["title"] == "Rain Tonight" and body["mood"] == "warm"
    assert body["artwork_url"].startswith("data:image/png;base64,")
    assert body["engine"] == {"transcription": "muse-voice-transcribe-1.0", "prompt": "muse-spark-1.3", "image": "muse-image-1.0"}


@pytest.mark.parametrize("failing,expect_image", [("generations", "svg"), ("completions", "png"), ("transcribe", "png")])
def test_each_meta_failure_degrades_gracefully(client, failing, expect_image):
    handler, _ = meta_handler(fail=(failing,))
    meta_ai._TRANSPORT = httpx.MockTransport(handler)
    try:
        login(client)
        r = generate(client)
    finally:
        meta_ai._TRANSPORT = None
    assert r.status_code == 200
    body = r.json()
    assert body["artwork_url"].startswith(f"data:image/{'svg+xml' if expect_image == 'svg' else 'png'}")
    assert body["prompt"] and body["title"] and body["mood"]


def test_runs_locally_without_a_key(monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    monkeypatch.delenv("META_API_KEY", raising=False)
    c = TestClient(main.app, follow_redirects=False)
    login(c)
    body = generate(c, "surprise").json()
    assert body["meta_ai"] is False and body["artwork_url"].startswith("data:image/svg+xml")
    assert body["transcript"] is None and body["prompt"]
