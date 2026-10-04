"""Ticket 13: /api/recording/results WebSocket wiring.

The orchestrator-level forwarding/stays-attached-across-finals/closes-on-stop
behaviour is covered against a fake channel in test_streaming_orchestrator.py
(test_interim_and_final_results_are_forwarded_to_an_attached_channel,
test_results_channel_stays_attached_across_an_interim_final_result,
test_stop_detaches_and_closes_the_results_channel,
test_has_results_channel_is_false_until_one_is_attached).

A live two-WebSocket scenario (results + audio open concurrently) was
deliberately not added at this layer: it requires both sockets, plus the
POST that starts the orchestrator, to share one TestClient portal/event
loop (nested `websocket_connect` calls each spin up their own throwaway
portal otherwise, and results/audio coordinate through one asyncio.Queue
that can't be safely awaited across loops). Entering a shared portal binds
the process-wide singletons' (recording_session, audio_registry,
silence_monitor) event-loop-bound internals to a loop that's torn down at
the end of the scenario, corrupting every later test module that relies on
the suite's default (per-call, throwaway-portal) TestClient behaviour --
observed directly while developing this ticket as spurious CancelledError
failures in unrelated modules. The connection-gating rule itself
(`/api/recording/stream` requires `streaming_orchestrator.has_results_channel`)
is simple enough to read directly off `main.py`.
"""

import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app, recording_session, audio_registry, note, streaming_orchestrator

client = TestClient(app)


def teardown_module(module) -> None:
    client.close()


def setup_function():
    asyncio.run(recording_session.reset())
    asyncio.run(audio_registry.clear())
    note.text = ""
    note.saved_text = None
    streaming_orchestrator.reset()
    streaming_orchestrator._results_channel = None


def test_stream_rejects_connection_when_no_results_channel_is_attached():
    """Covered again (more thoroughly, with recovery) in
    test_recording_stream_ws.py; kept here too as this module's one
    ticket-13-focused assertion on the gating rule itself."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    client.post("/api/recording/start")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/recording/stream"):
            pass

    assert exc_info.value.code == 4410
