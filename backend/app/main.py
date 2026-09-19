from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audio_sources import AudioSource, AudioSourceRegistry, UnknownAudioSource
from .recording import InvalidRecordingTransition, RecordingSession
from .silence_timeout import SilenceTimeoutMonitor

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


@app.post("/api/recording/start")
async def start_recording():
    result = await _transition(recording_session.start)
    silence_monitor.start()
    return result


@app.post("/api/recording/pause")
async def pause_recording():
    # Mic is already off while paused, so Silence Timeout does not apply.
    result = await _transition(recording_session.pause)
    silence_monitor.cancel()
    return result


@app.post("/api/recording/resume")
async def resume_recording():
    result = await _transition(recording_session.resume)
    silence_monitor.start()
    return result


@app.post("/api/recording/stop")
async def stop_recording():
    silence_monitor.cancel()
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
    return await _transition(recording_session.stop)
