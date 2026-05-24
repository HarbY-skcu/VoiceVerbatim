import pytest
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
  assert t_r.mic_id == test_audio.get_default_input_device_info()['index']

def test_valid_microphone_setup():
  t_r = AudioRecorder()
  mic_id = random.choice(t_r._retrieve_input_devices())
  assert t_r.setup_microphone(mic_id)
  assert t_r.mic_id is not None

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