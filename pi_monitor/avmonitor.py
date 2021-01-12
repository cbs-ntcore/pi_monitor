"""
Web server running on a pi with a camera and microphone
"""

import os
import threading
import time
import wave

import pyaudio

from . import backend
from . import camera
from . import filesystem
from . import mic
from . import sysctl


stream_config = {
    'format': pyaudio.paInt16,
    'channels': 1,
    'rate': 256000,
    'frames_per_buffer': 2048,
    'input': True,
}


def find_audio_device_index_by_pattern(interface, pattern):
    info = interface.get_host_api_info_by_index(0)
    numdevices = info.get('deviceCount')

    for i in range(numdevices):
        dev_info = interface.get_device_info_by_host_api_device_index(0, i)
        if dev_info.get('maxInputChannels') > 0:
            name = dev_info.get('name')
            if re.match(pattern, name):
                return i
    raise Exception(f"No device found with name {name}")


class Mic(threading.Thread):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

        self.running = False

        self.wav_file = None
        self.stream = None

    def run(self):
        self.running = True
        try:
            self.interface = pyaudio.PyAudio()
        except Exception as e:
            logging.error(f"Failed to open audio interface: {e}")
            self.running = False
            return

        open_stream_cfg = stream_config.copy()
        open_stream_cfg['input_device_index'] = find_audio_device_index_by_pattern(
            self.interface, 'Pettersson')

        # compute delay time to wait 1/2 buffer
        buffer_delay_s = (
            open_stream_config['frames_per_buffer'] / open_stream_config['rate'])

        while self.running:
            # by default, wait 1 ms
            delay_s = 0.001
            with self.lock:
                if self.wav_file is not None:
                    if self.stream is None:
                        # stream has not yet been opened, open stream
                        self.stream = self.interface.open(**open_stream_cfg)
                    bs = self.stream.read(open_stream_config['frames_per_buffer'])
                    self.wav_file.writeframes(bs)
                    # stream.read will block up to 1 buffer so wait a bit longer
                    # to allow function outside thread to modify state
                    delay_s = buffer_delay_s
                else:  # wav_file is None
                    # file is None/closed, close stream
                    if self.stream is not None:
                        self.stream.stop_stream()
                        self.stream.close()
                        self.stream = None
            time.sleep(delay_s)

        self.interface.terminate()

    def _open_wav_file(self, filename):
        """Do not call this without first acquiring the lock"""
        self.wav_file = wave.open(filename, 'wb')
        self.wav_file.setnchannels(stream_config['channels'])
        self.wav_file.setframerate(stream_config['rate'])
        self.wav_file.setsampwidth(pyaudio.get_sample_size(stream_config['format']))

    def start_recording(self, filename):
        with self.lock:
            self._open_wav_file(filename)

    def split_recording(self, filename):
        with self.lock:
            self.wav_file.close()
            self._open_wav_file(filename)

    def stop_recording(self):
        with self.lock:
            self.wav_file.close()
            self.wav_file = None

    def stop(self):
        with self.lock:
            self.running = False
        self.join()


class AVThread(camera.CameraThread):
    def __init__(self):
        super().__init__()
        self.mic = Mic()

    def start_recording(self):
        super().start_recording()
        # use self.filename to make audio filename
        self.mic.start_recording(
            os.path.splitext(self.filename) + '.wav')

    def split_recording(self):
        super().split_recording()
        self.mic.split_recording(
            os.path.splitext(self.filename) + '.wav')

    def stop_recording(self):
        super().stop_recording()
        self.mic.stop_recording()

    def start(self):
        super().start()
        self.mic.start()

    def stop(self):
        super().stop()
        self.mic.stop()


def run(*args, **kwargs):
    backend.register(
        AVThread, r'^/camera/.??',
        init=lambda o: o.start(), deinit=lambda o: o.stop())
    #backend.register(
    #    camera.CameraThread, r'^/camera/.??',
    #    init=lambda o: o.start(), deinit=lambda o: o.stop())
    #backend.register(
    #    mic.MicThread, r'^/mic/.*',
    #    init=lambda o: o.start(), deinit=lambda o: o.stop())
    backend.register(
        sysctl.SystemControl, r'^/system/.??')
    backend.register(
        filesystem.FileSystem, r'^/filesystem/.??')
    backend.serve(*args, **kwargs)
