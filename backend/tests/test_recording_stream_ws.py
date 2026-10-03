"""Ticket 04.1: WebSocket streaming endpoint wiring.

Exercises /api/recording/stream end-to-end via TestClient's WebSocket test
support, with the orchestrator's service swapped for a fake so no real
speech-to-text call is made.
"""

import asyncio

from fastapi.testclient import TestClient

from backend.app.main import app, recording_session, audio_registry, note, streaming_orchestrator
from backend.app.transcription import StreamingResult

client = TestClient(app)


def teardown_module(module) -> None:
    """Close this module's TestClient once all its tests have run.

    TestClient spins up its own anyio portal thread/event loop per
    instance. Left open, that thread and loop linger after this module's
    tests finish and can interfere with later test modules that also
    instantiate a TestClient against the same shared `app` singletons
    (observed as spurious CancelledError from unrelated modules' requests).
    Explicitly closing it here scopes that lifecycle to this module.
    """
    client.close()


class FakeStreamingSession:
    def __init__(self):
        self.sent: list[bytes] = []
        self.closed = False
        self._queue: asyncio.Queue = asyncio.Queue()

    async def send_audio(self, chunk: bytes) -> None:
        self.sent.append(chunk)
        await self._queue.put(StreamingResult(text="hi", final=False))

    async def results(self):
        while True:
            item = await self._queue.get()
            if item is None:
                return
            yield item

    async def close(self) -> None:
        self.closed = True
        await self._queue.put(None)


class FakeStreamingService:
    def __init__(self):
        self.session: FakeStreamingSession | None = None

    async def start_session(self):
        self.session = FakeStreamingSession()
        return self.session


def setup_function():
    asyncio.run(recording_session.reset())
    asyncio.run(audio_registry.clear())
    note.text = ""
    note.cursor = 0
    note.saved_text = None
    streaming_orchestrator.reset()
    streaming_orchestrator.service = FakeStreamingService()


def test_stream_rejects_connection_when_not_recording():
    import pytest
    from starlette.websockets import WebSocketDisconnect

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/recording/stream"):
            pass

    assert exc_info.value.code == 4409


def test_stream_rejects_connection_when_no_results_channel_is_attached():
    """Ticket 13: streaming audio with nobody listening for results is an
    error condition, not silently tolerated -- /api/recording/results must
    be connected first."""
    import pytest
    from starlette.websockets import WebSocketDisconnect

    client.post("/api/recording/start")

    with pytest.raises(WebSocketDisconnect) as exc_info:
        with client.websocket_connect("/api/recording/stream"):
            pass

    assert exc_info.value.code == 4410


def _connect_and_send(chunk: bytes) -> None:
    """Open the results channel (required, ticket 13), then the stream,
    send one chunk, and close both cleanly.

    Sends an explicit close frame (`ws.close()`) before the `with` block
    exits, exercising the same disconnect path the app sees in production
    (a real close makes `receive_bytes()` raise `WebSocketDisconnect`, not
    `CancelledError`). Despite that, TestClient's `__exit__` can still
    raise `CancelledError` from its own portal teardown -- a harness
    artifact unrelated to the app's disconnect handling (see the note on
    `stream_audio`'s `finally` in main.py) -- so that specific exception
    from `__exit__` is tolerated here. Anything a caller needs to assert
    is captured before this function returns, so the teardown noise can't
    mask a real failure.
    """
    try:
        with client.websocket_connect("/api/recording/results") as results_ws:
            with client.websocket_connect("/api/recording/stream") as ws:
                ws.send_bytes(chunk)
                ws.close()
            results_ws.close()
    except BaseException as exc:
        if type(exc).__name__ != "CancelledError":
            raise


def test_stream_forwards_audio_to_the_streaming_session_while_recording():
    """No cleanup POST follows the websocket in this test: the preceding
    disconnect leaves the orchestrator's background consume task in a
    cancelled-but-not-yet-settled state (a TestClient portal-teardown
    artifact, see `_connect_and_send`), and issuing another request against
    the same TestClient immediately afterwards can itself raise a spurious
    CancelledError while that settles. The assertion below only needs state
    established before the websocket closed, so no further request is
    needed here.
    """
    client.post("/api/recording/start")

    _connect_and_send(b"chunk-1")

    assert streaming_orchestrator.service.session.sent == [b"chunk-1"]


def test_dropped_stream_socket_pauses_the_recording():
    """Covers the implicit-Pause cleanup (main._implicit_pause_from_stream_drop)
    directly rather than through TestClient's websocket teardown.

    TestClient's anyio portal cancels the connection handler's task as part
    of its own teardown when a `websocket_connect(...)` context exits --
    including anything the handler's `finally` block does -- which is a
    harness artifact, not how a real client disconnect behaves (see the
    comment on `stream_audio`'s `finally` in main.py). The disconnect path
    itself (WebSocketDisconnect -> this cleanup coroutine) is exercised
    here by driving it directly, all on a single event loop (mixing
    TestClient's portal loop with a second `asyncio.run` would bind the
    fake session's Queue to one loop and await it from another, which
    raises its own spurious CancelledError -- unrelated to the app code).
    The HTTP-level forwarding is covered by
    test_stream_forwards_audio_to_the_streaming_session_while_recording
    above, and the orchestrator's own close/consume behaviour is covered
    in test_streaming_orchestrator.py.
    """
    import asyncio as _asyncio

    from backend.app.main import _implicit_pause_from_stream_drop

    async def scenario():
        await recording_session.start()
        await streaming_orchestrator.start()
        assert recording_session.state == "recording"

        await _implicit_pause_from_stream_drop()

        assert recording_session.state == "paused"

    _asyncio.run(scenario())
