import asyncio
import base64

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audio_buffer import AudioBuffer
from .audio_sources import AudioSource, AudioSourceRegistry, UnknownAudioSource
from .note import ActiveNote
from .recording import InvalidRecordingTransition, RecordingSession
from .silence_timeout import SilenceTimeoutMonitor

from .streaming_orchestrator import StreamingTranscriptionOrchestrator
from .transcription import (
    StreamingTranscriptionSession,
    TranscriptionError,
)
from .transcription_pipeline import TranscriptionPipeline

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
pipeline = TranscriptionPipeline(
    buffer=AudioBuffer(), note=note, service=UnconfiguredTranscriptionService()
)

streaming_orchestrator = StreamingTranscriptionOrchestrator(
    note=note, service=UnconfiguredStreamingTranscriptionService()
)

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
    pipeline.buffer.append(base64.b64decode(payload.data))
    return {"ok": True}


async def _implicit_pause_from_stream_drop() -> None:
    await streaming_orchestrator.stop()
    try:
        await recording_session.pause()
    except InvalidRecordingTransition:
        pass
    else:
        silence_monitor.cancel()


@app.websocket("/api/recording/stream")
async def stream_audio(websocket: WebSocket):
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
        await _implicit_pause_from_stream_drop()


@app.post("/api/recording/start")
async def start_recording():
    result = await _transition(recording_session.start)
    silence_monitor.start()
    await streaming_orchestrator.start()
    return result


@app.post("/api/recording/pause")
async def pause_recording():
    result = await _transition(recording_session.pause, with_transcription=True)
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
    return await _transition(recording_session.stop, with_transcription=True)


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
    return await _transition(recording_session.stop)
    # return await _transition(recording_session.stop, with_transcription=True)
    # await streaming_orchestrator.stop()
    # return await _transition(recording_session.stop, with_transcription=True)
