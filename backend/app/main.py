import asyncio
import base64

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audio_buffer import AudioBuffer
from .audio_sources import AudioSource, AudioSourceRegistry, UnknownAudioSource
from .note import ActiveNote
from .note_store import NoteTitleGenerator
from .recording import InvalidRecordingTransition, RecordingSession
from .silence_timeout import SilenceTimeoutMonitor



from .transcription import TranscriptionError


from .streaming_orchestrator import StreamingTranscriptionOrchestrator
from .transcription import (
    StreamingTranscriptionSession,
    TranscriptionError,
)
from .transcription_pipeline import TranscriptionPipeline
from .vosk_transcription import VoskStreamingTranscriptionService, _load_model

app = FastAPI(title="Voice-to-Text Notes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SIDEBAR_TABS = ["All Notes", "Bookmarks"]

audio_registry = AudioSourceRegistry()
recording_session = RecordingSession()


async def _on_silence_timeout() -> None:
    """Fires when the Silence Timeout window passes with no new
    transcription text during an active Recording. Behaves identically to
    a manual Stop: tears down the streaming orchestrator (closing the
    results channel, which is the frontend's cue to resync to idle) and
    transitions the Recording session itself."""
    await streaming_orchestrator.stop()
    try:
        await recording_session.stop()
    except InvalidRecordingTransition:
        pass


silence_monitor = SilenceTimeoutMonitor(_on_silence_timeout)


class UnconfiguredTranscriptionService:
    """Default transcription backend until a real one is wired in.

    Ticket 04 owns the pipeline (buffer -> transcribe -> insert -> save);
    the actual speech-to-text integration is out of scope here, so the
    default surfaces a clear, non-corrupting error instead of pretending
    to transcribe.
    """

    async def transcribe(self, audio: bytes) -> str:
        raise TranscriptionError("Transcription service not configured")


class UnconfiguredStreamingTranscriptionSession:
    """Session used until a real streaming speech-to-text backend is wired
    in. Accepts audio silently (per ticket 04.1's scope: the mic->socket
    path is landed end-to-end, but nothing consumes the audio yet) and
    never yields a result.
    """

    async def send_audio(self, chunk: bytes) -> None:
        pass

    async def results(self):
        return
        yield  # pragma: no cover - makes this an async generator

    async def close(self) -> None:
        pass


class UnconfiguredStreamingTranscriptionService:
    async def start_session(self) -> StreamingTranscriptionSession:
        return UnconfiguredStreamingTranscriptionSession()


note = ActiveNote()
note_titles = NoteTitleGenerator()
pipeline = TranscriptionPipeline(
    buffer=AudioBuffer(), note=note, service=UnconfiguredTranscriptionService()
)
streaming_orchestrator = StreamingTranscriptionOrchestrator(
    service=VoskStreamingTranscriptionService(),
    # Every result (interim or final) counts as "still talking" for the
    # Silence Timeout window -- see silence_timeout.py.
    on_result=lambda: silence_monitor.notify_speech(),
)


@app.on_event("startup")
async def _preload_transcription_model() -> None:
    """Preloads the Vosk model off the event loop at startup.

    Loading parses ~2-3GB of files and can take tens of seconds; doing it
    lazily on the first streaming request would make that request (and
    every other one queued behind it on the event loop) hang. Doing it
    here, during startup, pays that cost once up front instead.
    """
    await asyncio.to_thread(_load_model)





@app.get("/api/sidebar/tabs")
def get_sidebar_tabs():
    return {"tabs": SIDEBAR_TABS, "active": SIDEBAR_TABS[0]}


class AudioSourceIn(BaseModel):
    id: str
    label: str = ""


class RegisterAudioSourcesIn(BaseModel):
    sources: list[AudioSourceIn]


class SetActiveAudioSourceIn(BaseModel):
    id: str


class AudioChunkIn(BaseModel):
    data: str


@app.get("/api/audio/sources")
def get_audio_sources():
    return audio_registry.snapshot()


@app.put("/api/audio/sources")
async def register_audio_sources(payload: RegisterAudioSourcesIn):
    return await audio_registry.register(
        [AudioSource(id=s.id, label=s.label) for s in payload.sources]
    )


@app.put("/api/audio/sources/active")
async def set_active_audio_source(payload: SetActiveAudioSourceIn):
    try:
        return await audio_registry.set_active(payload.id)
    except UnknownAudioSource:
        raise HTTPException(
            status_code=400, detail=f"Unknown audio source: {payload.id}"
        )


@app.get("/api/recording")
def get_recording_state():
    return {"state": recording_session.state}


@app.get("/api/note")
def get_active_note():
    """Ticket 14: the Note being built from the flowing transcript.

    `text` is whatever the frontend last pushed via `PUT /api/note`
    (full-text overwrite -- ticket 14 moved composition/positioning
    ownership to the frontend, so this may lag the live stream by design,
    see streaming_orchestrator.py); `title` is the gap-filling
    "Untitled N" placeholder assigned at record start until ticket 06's
    auto-generation/manual-edit lands.
    """
    return {"title": note.title, "text": note.text}


class NoteTextIn(BaseModel):
    text: str


@app.put("/api/note")
def update_active_note(payload: NoteTextIn):
    """Ticket 14: the frontend's full-text overwrite.

    The frontend owns composition/positioning entirely now -- it splices
    transcription results and manual edits into its own locally-tracked
    text, then pushes the resulting full text here (debounced for manual
    edits, immediate for transcription results and on
    Record/Stop/navigation-stop). The backend is a dumb sink: no
    splicing, no cursor.
    """
    note.set_text(payload.text)
    note.save()
    return {"title": note.title, "text": note.text}


async def _transition(action, *, with_transcription: bool = False):
    try:
        state = await action()
    except InvalidRecordingTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    result = {"state": state}
    if with_transcription:
        result["transcription"] = await pipeline.flush_and_transcribe()
    return result


@app.post("/api/recording/audio-chunk")
async def append_audio_chunk(payload: AudioChunkIn):
    """Legacy batch ingest, kept for the buffered path (ticket 04) while the
    real-time streaming path (ticket 04.1, `/api/recording/stream`) is the
    seam new clients should use.
    """
    pipeline.buffer.append(base64.b64decode(payload.data))
    return {"ok": True}


async def _implicit_stop_from_stream_drop() -> None:
    """A dropped/closed streaming socket is treated identically to a manual
    Stop: the mic is gone, so recording stops (idle Recordings never
    reach here since the socket only accepts frames while recording).

    No transcription flush is forced here -- same as Navigation Stop, this
    fires from an event that ended input rather than a deliberate user
    action, and the streaming path already commits transcribed text
    incrementally via the results socket as it arrives.
    """
    silence_monitor.cancel()
    await streaming_orchestrator.stop()
    try:
        await recording_session.stop()
    except InvalidRecordingTransition:
        pass


@app.websocket("/api/recording/results")
async def stream_results(websocket: WebSocket):
    """Real-time transcription-results delivery (ticket 13), the outbound
    counterpart to `/api/recording/stream`'s inbound audio.

    Must be connected *before* `/api/recording/stream` will accept audio
    (see `stream_audio` below) -- streaming audio with nobody listening for
    results is treated as an error condition, not silently tolerated.

    Stays open for the entire Recording regardless of how many interim/
    final results are forwarded along the way (a long dictation session
    with natural pauses between sentences produces many); it only closes
    once the orchestrator's `stop()` actually ends the Recording (manual
    Stop, Navigation Stop, Silence Timeout, or a dropped audio socket).
    """
    await websocket.accept()
    channel = WebSocketResultsChannel()
    streaming_orchestrator.attach_results_channel(channel)
    try:
        # This handler task is the *sole* owner of `websocket`: it's the
        # only coroutine that ever calls send/receive/close on it. The
        # orchestrator's background consume task only ever touches
        # `channel`, which hands messages across via an asyncio.Queue --
        # two coroutines both driving one Starlette WebSocket at once
        # (e.g. one sending while another receives) can deadlock the
        # connection, so that's deliberately avoided.
        while True:
            message = await channel.next_message()
            if message is None:
                break
            await websocket.send_json(message)
    except WebSocketDisconnect:
        pass
    finally:
        streaming_orchestrator.detach_results_channel(channel)
        channel.mark_closed()
        try:
            await websocket.close()
        except Exception:
            pass


class WebSocketResultsChannel:
    """Queues streaming transcription results for the results-socket
    handler task to forward, without ever touching the WebSocket itself.

    Two distinct ways this ends, both idempotent via `_closed`:
    - `close()`: the orchestrator decided the Recording actually ended
      (manual Stop, Navigation Stop, Silence Timeout, dropped audio
      socket) and is telling this channel's consumer (`stream_results`)
      to stop waiting for more -- pushes a `None` sentinel so the
      handler's loop breaks and closes the WebSocket.
    - `mark_closed()`: the *consumer* side ended first (e.g. the results
      WebSocket itself disconnected) -- stops accepting/queuing further
      `send()` calls, but doesn't push a sentinel since nobody's left to
      read it.
    """

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._closed = False

    async def send(self, *, text: str, final: bool) -> None:
        if self._closed:
            return
        await self._queue.put({"text": text, "final": final})

    async def close(self) -> None:
        """The orchestrator ending the Recording -- signal the consumer
        (`stream_results`) to stop via a sentinel, then stop accepting
        further sends."""
        if self._closed:
            return
        self._closed = True
        await self._queue.put(None)

    async def next_message(self) -> dict | None:
        return await self._queue.get()

    def mark_closed(self) -> None:
        self._closed = True


@app.websocket("/api/recording/stream")
async def stream_audio(websocket: WebSocket):
    """Real-time audio ingest (ticket 04.1), replacing the buffered
    /api/recording/audio-chunk POST for streaming clients. Only accepts
    frames while a Recording is active, and only once a results channel
    (ticket 13, `/api/recording/results`) is already attached -- audio with
    nowhere for its transcription to go is rejected outright. Closing the
    socket (deliberately or via a dropped connection) is treated as an
    implicit Stop.
    """
    if recording_session.state != "recording":
        await websocket.close(code=4409, reason="No active Recording")
        return
    if not streaming_orchestrator.has_results_channel:
        await websocket.close(code=4410, reason="No results channel connected")
        return

    await websocket.accept()
    try:
        while True:
            chunk = await websocket.receive_bytes()
            await streaming_orchestrator.send_audio(chunk)
    except WebSocketDisconnect:
        pass
    finally:
        # A plain, direct await. Note for future maintainers: FastAPI's
        # TestClient (via anyio's asyncio backend) cancels this handler's
        # whole task tree -- including tasks spawned from within it,
        # shielded or not -- as part of its own connection teardown, which
        # is not how a real client disconnect behaves (a real disconnect
        # just makes `receive_bytes()` raise `WebSocketDisconnect` and this
        # `finally` runs to completion normally, as covered directly by
        # test_streaming_orchestrator.py). Under TestClient specifically
        # this cleanup can be cut off mid-way; that's a known harness
        # limitation, not production behaviour, so it isn't worked around
        # here.
        await _implicit_stop_from_stream_drop()


@app.post("/api/recording/start")
async def start_recording():
    result = await _transition(recording_session.start)
    if note.title is None:
        # Note is created on record start as "Untitled N" (gap-filling);
        # read-only during recording, editable after stop (ticket 14).
        note.title = note_titles.next_title()
    silence_monitor.start()
    await streaming_orchestrator.start()
    return result


@app.post("/api/recording/stop")
async def stop_recording():
    silence_monitor.cancel()
    await streaming_orchestrator.stop()
    return await _transition(recording_session.stop, with_transcription=True)


@app.post("/api/recording/navigation-stop")
async def navigation_stop():
    """Called when the user navigates away from the current Note view.
    Behaves identically to a manual Stop. A no-op if no Recording is
    active, since navigating away with nothing running is not an error."""
    if recording_session.state == "idle":
        return {"state": recording_session.state}
    silence_monitor.cancel()

    await streaming_orchestrator.stop()
    return await _transition(recording_session.stop, with_transcription=False)

    # await streaming_orchestrator.stop()
    # return await _transition(recording_session.stop, with_transcription=True)

