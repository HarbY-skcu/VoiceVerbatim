from collections.abc import Mapping
from typing import AsyncGenerator

import pyaudio
import asyncio



class AudioRecorder:
  CHUNK = 1024

  def __init__(self):
    self._mic_id = None
    self._audio_format = pyaudio.paInt16
    self._audio_channel_types = [
      'Windows WASAPI'
    ]

    self._audio_driver = pyaudio.PyAudio()
    self._stream = None

    self._keep_stream_alive = False
    self._paused = False

    self._latest_chunk = None
    self._chunk_ready_event = None
    self._loop = None

  def callback(self, in_data, frame_count, time_info, status):
    if self._paused:
      return in_data, pyaudio.paContinue

    self._loop.call_soon_threadsafe(self._on_chunk, in_data)
    return in_data, pyaudio.paContinue

  def _on_chunk(self, in_data) -> None:
    self._latest_chunk = in_data
    self._chunk_ready_event.set()

  async def record_audio(self) -> AsyncGenerator[bytes, None]:
    self._initialize_events()
    self._stream = self._create_and_start_stream()
    try:
      while self._keep_stream_alive:
        await self._chunk_ready_event.wait()
        self._chunk_ready_event.clear()
        if not self._keep_stream_alive:
          break
        if self._latest_chunk is None:
          continue
        yield self._latest_chunk
    finally:
      self._end_and_cleanup_stream()

  def _initialize_events(self) -> None:
    self._loop = asyncio.get_running_loop()
    self._chunk_ready_event = asyncio.Event()

  def _create_and_start_stream(self) -> pyaudio.PyAudio.Stream:
    stream = self._open_stream()
    stream.start_stream()
    self._keep_stream_alive = True
    return stream

  def _end_and_cleanup_stream(self) -> None:
    self._stream.stop_stream()
    self._stream.close()
    self._stream = None

  def close_stream(self) -> None:
    self._keep_stream_alive = False
    self._paused = False
    if self._chunk_ready_event is not None:
        self._chunk_ready_event.set()

  def pause_stream(self) -> None:
    self._paused = True
    self._latest_chunk = None
    self._chunk_ready_event.clear()

  def unpause_stream(self) -> None:
    self._paused = False

  def _open_stream(self) -> pyaudio.PyAudio.Stream:
    return self._audio_driver.open(
      format=self._audio_format,
      channels=1,
      rate=int(self._get_device_info(self._mic_id)['defaultSampleRate']),
      input_device_index=self._mic_id,
      input=True,
      frames_per_buffer=AudioRecorder.CHUNK,
      stream_callback=self.callback
    )

  def setup_microphone(self, mic_id = None) -> bool:
    list_of_input_ids = self._retrieve_input_devices()
    if mic_id is None:
      try:
        self._mic_id = self._get_default_device_id()
        return True
      except OSError as e:
        return False
    elif mic_id in list_of_input_ids:
      self._mic_id = mic_id
      return True
    else:
      return False

  def _get_default_device_id(self) -> int:
    return self._audio_driver.get_default_input_device_info()['index']

  def _retrieve_input_devices(self) -> list[int]:
    input_id_list = list()
    for index in range(self._audio_driver.get_device_count()):
      info = self._get_device_info(index)
      host_index = info['hostApi']
      host_api_info = self._get_host_api_info(host_index)
      num_of_inputs = info['maxInputChannels']
      if host_api_info['name'] in self._audio_channel_types and num_of_inputs > 0:
        input_id_list.append(index)
    return input_id_list

  def _get_device_info(self, index: int) -> Mapping[str, str | int | float]:
    return self._audio_driver.get_device_info_by_index(index)

  def _get_host_api_info(self, host_index: int) -> Mapping[str, str | int]:
    return self._audio_driver.get_host_api_info_by_index(host_index)