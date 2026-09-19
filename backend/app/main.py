import base64

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audio_buffer import AudioBuffer
from .audio_sources import AudioSource, AudioSourceRegistry, UnknownAudioSource
from .note import ActiveNote
from .recording import InvalidRecordingTransition, RecordingSession
from .transcription import TranscriptionError
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


class UnconfiguredTranscriptionService:
    """Default transcription backend until a real one is wired in.

    Ticket 04 owns the pipeline (buffer -> transcribe -> insert -> save);
    the actual speech-to-text integration is out of scope here, so the
    default surfaces a clear, non-corrupting error instead of pretending
    to transcribe.
    """

    async def transcribe(self, audio: bytes) -> str:
        raise TranscriptionError("Transcription service not configured")


note = ActiveNote()
pipeline = TranscriptionPipeline(
    buffer=AudioBuffer(), note=note, service=UnconfiguredTranscriptionService()
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


@app.post("/api/recording/start")
async def start_recording():
    return await _transition(recording_session.start)


@app.post("/api/recording/pause")
async def pause_recording():
    # Pause flushes the current audio buffer for transcription (ticket 04);
    # Resume then starts against an empty buffer.
    return await _transition(recording_session.pause, with_transcription=True)


@app.post("/api/recording/resume")
async def resume_recording():
    return await _transition(recording_session.resume)


@app.post("/api/recording/stop")
async def stop_recording():
    return await _transition(recording_session.stop, with_transcription=True)
