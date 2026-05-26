from datetime import date
from typing import Annotated

from pydantic import BaseModel, Field

class Microphone(BaseModel):
  device_index: Annotated[
    int | None,
    Field(
      alias="deviceId",
      description="Index of selected microphone"
    )
  ] = None

class TranscriptText(BaseModel):
  words: Annotated[str, Field(description="stream of transcribed text")]
  timestamp: Annotated[date, Field(description="timestamp of transcribed text")]

class IncomingAudio(BaseModel):
  size: Annotated[int, Field(gt=0,lt=1000, description="size of data being sent")]
  timestamp: Annotated[date, Field(description="timestamp of recorded audio")]
