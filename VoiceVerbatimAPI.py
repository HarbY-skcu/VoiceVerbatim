from typing import Annotated
from collections.abc import AsyncIterable, Iterable

from fastapi import FastAPI, APIRouter, Path, Body
from fastapi.sse import EventSourceResponse
import requests
from APIRequestAndResponseSchema import TranscriptText, Microphone, IncomingAudio


def create_fastapi_app() -> FastAPI:
  return FastAPI()

class NotesRouter:

  def __init__(self):
    self.router = APIRouter(
      prefix = "/notes",
      tags = ["notes"]
    )

    self.router.add_api_route(
      "/{note_id}/stream",
      self.transcribe_notes,
      methods=['POST'],
      response_class = EventSourceResponse
    )

  async def transcribe_notes(self):
    pass
    # 1. Go to microphone function, and yield audio stream
    # 2. Go to transcription function, directing audio stream, and yielding a text stream
    # 3. Yield text stream to client
    # 4. If pause occurs, wait the text stream
    # 5. If error occurs, or stop is called, end the text stream.

  # async def transcribe_notes(
  #     self,
  #     note_id: Annotated[str, Path(title='Note to generate')],
  #     microphone_settings: Annotated[Microphone, Body()]
  # ) -> AsyncIterable[TranscriptText]:
  #   while True:
  #     with requests.get(
  #       url='placeholder',
  #       stream=True,
  #       headers = microphone_settings.model_dump()
  #     ) as response:
  #       response.raise_for_status()
  #       IncomingAudio.model_validate(response)
  #       for chunk in response.iter_content(chunk_size=0):
  #         yield #hypothetical function taking chunk, and outputting streamed text
  #     break

    pass