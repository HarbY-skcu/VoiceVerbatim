"""Seam under test: the FastAPI `startup` event that preloads the Vosk
model in `main.py`.

Uses a monkeypatched `_load_model` so this test doesn't require a real
(multi-GB) Vosk model on disk, and only opens the TestClient as a context
manager here (which is what actually triggers FastAPI's startup/shutdown
lifespan events) -- other test modules use a bare `TestClient(app)` without
the `with` form specifically so they *don't* trigger this hook.
"""

import threading

from fastapi.testclient import TestClient

import backend.app.vosk_transcription as vosk_transcription
from backend.app.main import app


def test_startup_preloads_the_model_off_the_event_loop(monkeypatch):
    main_thread = threading.current_thread()
    load_thread = None
    calls = []

    def fake_load_model(model_path=None):
        nonlocal load_thread
        load_thread = threading.current_thread()
        calls.append(model_path)
        return object()

    monkeypatch.setattr(vosk_transcription, "_load_model", fake_load_model)
    # main.py imported `_load_model` directly into its own namespace, so the
    # patch needs to apply there too.
    monkeypatch.setattr("backend.app.main._load_model", fake_load_model)

    with TestClient(app):
        pass

    assert calls, "expected _load_model to be called during startup"
    assert load_thread is not None
    assert load_thread is not main_thread
