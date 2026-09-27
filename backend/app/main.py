from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audio_sources import AudioSource, AudioSourceRegistry, UnknownAudioSource
from .note import ActiveNote
from .recording import InvalidRecordingTransition, RecordingSession
from .silence_timeout import SilenceTimeoutMonitor
from .streaming_orchestrator import StreamingTranscriptionOrchestrator
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
    """Fires when 15s pass with no transcribed speech during an active
    Recording. Behaves identically to a manual Stop."""
    try:
        await recording_session.stop()
    except InvalidRecordingTransition:
        pass


silence_monitor = SilenceTimeoutMonitor(_on_silence_timeout)


note = ActiveNote()
streaming_orchestrator = StreamingTranscriptionOrchestrator(
    note=note, service=VoskStreamingTranscriptionService()
)


@app.on_event("startup")
async def _preload_vosk_model() -> None:
    """Loads the (multi-GB) Vosk model once at process startup, off the
    event loop, so the first /api/recording/start call isn't the one that
    pays the multi-second/minute parsing cost."""
    import asyncio

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


async def _transition(action):
    try:
        state = await action()
    except InvalidRecordingTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {"state": state}


async def _implicit_pause_from_stream_drop() -> None:
    """A dropped/closed streaming socket is treated identically to a manual
    Pause: the mic is gone, so recording pauses (idle Recordings never
    reach here since the socket only accepts frames while recording).
    """
    await streaming_orchestrator.stop()
    try:
        await recording_session.pause()
    except InvalidRecordingTransition:
        pass
    else:
        silence_monitor.cancel()


@app.websocket("/api/recording/stream")
async def stream_audio(websocket: WebSocket):
    """Real-time audio ingest. Only accepts frames while a Recording is
    active; closing the socket (deliberately or via a dropped connection)
    is treated as an implicit Pause.
    """
    if recording_session.state != "recording":
        await websocket.close(code=4409, reason="No active Recording")
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
        await _implicit_pause_from_stream_drop()


@app.post("/api/recording/start")
async def start_recording():
    result = await _transition(recording_session.start)
    silence_monitor.start()
    await streaming_orchestrator.start()
    return result


@app.post("/api/recording/pause")
async def pause_recording():
    # Mic is already off while paused, so Silence Timeout does not apply.
    # Pause closes the streaming session, force-finalizing any trailing
    # partial utterance so it isn't lost; Resume then opens a fresh session.
    result = await _transition(recording_session.pause)
    silence_monitor.cancel()
    await streaming_orchestrator.stop()
    return result

@app.post("/api/recording/resume")
async def resume_recording():
    result = await _transition(recording_session.resume)
    silence_monitor.start()
    await streaming_orchestrator.start()
    return result


@app.post("/api/recording/stop")
async def stop_recording():
    silence_monitor.cancel()
    await streaming_orchestrator.stop()
    return await _transition(recording_session.stop)


@app.post("/api/recording/speech")
async def notify_transcribed_speech():
    """Called whenever new transcribed speech arrives during an active
    Recording. Resets the Silence Timeout window."""
    silence_monitor.notify_speech()
    return {"state": recording_session.state}


@app.post("/api/recording/navigation-stop")
async def navigation_stop():
    """Called when the user navigates away from the current Note view.
    Behaves identically to a manual Stop. A no-op if no Recording is
    active, since navigating away with nothing running is not an error."""
    if recording_session.state == "idle":
        return {"state": recording_session.state}
    silence_monitor.cancel()
    await streaming_orchestrator.stop()
    return await _transition(recording_session.stop)
