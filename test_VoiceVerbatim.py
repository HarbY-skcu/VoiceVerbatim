import asyncio
import time

import pytest
import pytest_asyncio
from fastapi import FastAPI
import VoiceVerbatimAPI as VVA
from Microphone import AudioRecorder
import pyaudio
import random

def test_create_app():
  assert isinstance(VVA.create_fastapi_app(), FastAPI)

def test_default_microphone_setup():
  t_r = AudioRecorder()
  mic_id = None
  test_audio = pyaudio.PyAudio()
  assert t_r.setup_microphone(mic_id)
  assert t_r._mic_id == test_audio.get_default_input_device_info()['index']

def test_valid_microphone_setup():
  t_r = AudioRecorder()
  mic_id = random.choice(t_r._retrieve_input_devices())
  assert t_r.setup_microphone(mic_id)
  assert t_r._mic_id is not None

def test_invalid_microphone_setup():
  t_r = AudioRecorder()
  invalid_mic_id =  random.choice(_retrieve_invalid_input_devices(t_r))
  assert not t_r.setup_microphone(invalid_mic_id)

def _retrieve_invalid_input_devices(t_r: AudioRecorder) -> list[int]:
  invalid_input_list = list()
  for i in range(t_r._audio_driver.get_device_count()):
    info = t_r._audio_driver.get_device_info_by_index(i)
    host_api_info = t_r._audio_driver.get_host_api_info_by_index(info['hostApi'])
    num_of_inputs = info['maxInputChannels']
    if host_api_info['name'] not in t_r._audio_channel_types or num_of_inputs == 0:
      invalid_input_list.append(i)
  return invalid_input_list

def test_retrieve_input_devices():
  t_r = AudioRecorder()
  list_of_devices = t_r._retrieve_input_devices()
  assert isinstance(list_of_devices, list)
  assert all(
    isinstance(item, int)
    for item in list_of_devices
  )
@pytest.mark.asyncio
async def test_default_microphone_audio_chunk_size():
  t_r = AudioRecorder()
  t_r.setup_microphone(None)
  start = time.perf_counter()
  async for chunk in t_r.record_audio():
    size = len(chunk)
    assert 1024 <= size <= 4096, f'Bad chunk size: {size}'
    if time.perf_counter() - start >= 3:
      t_r.close_stream()
      break

@pytest.mark.asyncio
async def test_random_microphone_audio_chunk_size():
  t_r = AudioRecorder()
  mic_id = random.choice(t_r._retrieve_input_devices())
  t_r.setup_microphone(mic_id)
  start = time.perf_counter()
  async for chunk in t_r.record_audio():
    size = len(chunk)
    assert 1024 <= size <= 4096, f'Bad chunk size: {size}'
    if time.perf_counter() - start >= 3:
      t_r.close_stream()
      break

@pytest.mark.asyncio
async def test_audio_stream_pause():
  t_r = AudioRecorder()
  t_r.setup_microphone(None)
  chunk_times = list()
  async for _ in t_r.record_audio():
    current_time = time.perf_counter()
    chunk_times.append(current_time)
    if len(chunk_times) == 5:
      t_r.pause_stream()
      await asyncio.sleep(2)
      t_r.unpause_stream()
    if len(chunk_times) >= 10:
      t_r.close_stream()
      break

  gaps = [
    chunk_times[i + 1] - chunk_times[i]
    for i in range(len(chunk_times) - 1)
  ]

  assert max(gaps) > 1.5

@pytest.mark.asyncio
async def test_close_while_paused():
  t_r = AudioRecorder()
  t_r.setup_microphone(None)
  async def controller():
    await asyncio.sleep(3)
    t_r.pause_stream()
    await asyncio.sleep(2)
    t_r.close_stream()
  controller_task = asyncio.create_task(controller())
  async for _ in t_r.record_audio():
    pass
  await controller_task
  assert t_r._stream is None