from abc import abstractmethod, ABC
from collections.abc import Mapping

import pyaudio
from pyaudio import PyAudio

class AudioRecorder:
  def __init__(self):
    self._mic_id = None
    self._audio_format = pyaudio.paInt16
    self._audio_channel_types = [
      'Windows WASAPI'
    ]
    self._audio_driver = pyaudio.PyAudio()

  def setup_microphone(self, mic_id = None) -> bool:
    list_of_input_ids = self._retrieve_input_devices()
    if mic_id is None:
      try:
        self.mic_id = self._audio_driver.get_default_input_device_info()['index']
        return True
      except OSError as e:
        return False
    elif mic_id in list_of_input_ids:
      self.mic_id = mic_id
      return True
    else:
      return False

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