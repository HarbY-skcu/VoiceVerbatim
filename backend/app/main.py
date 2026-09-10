from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .audio_sources import AudioSource, AudioSourceRegistry, UnknownAudioSource

app = FastAPI(title="Voice-to-Text Notes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SIDEBAR_TABS = ["All Notes", "Bookmarks"]

audio_registry = AudioSourceRegistry()


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
def register_audio_sources(payload: RegisterAudioSourcesIn):
    return audio_registry.register(
        [AudioSource(id=s.id, label=s.label) for s in payload.sources]
    )


@app.put("/api/audio/sources/active")
def set_active_audio_source(payload: SetActiveAudioSourceIn):
    try:
        return audio_registry.set_active(payload.id)
    except UnknownAudioSource:
        raise HTTPException(
            status_code=400, detail=f"Unknown audio source: {payload.id}"
        )
