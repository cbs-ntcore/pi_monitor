"""
Web server running on a pi with a camera and microphone
"""

import logging
import os
import re
import queue
import threading
import time
import wave

import pyaudio

from . import backend
from . import camera
from . import filesystem
from . import mic
from . import sysctl


class WavFileWriter(threading.Thread):
    def __init__(self, nchannels, rate, sampwidth):
        super().__init__()
        self.nchannels = nchannels
        self.rate = rate
        self.sampwidth = sampwidth
        self._q = queue.Queue()

    def run(self):
        f = None
        while True:
            v = self._q.get()
            if v is None:
                break
            elif isinstance(v, str):  # filename
                if len(v):  # new file
                    if f is not None:
                        f.close()
                        f = None
                    f = wave.open(v, 'wb')
                    f.setnchannels(self.nchannels)
                    f.setframerate(self.rate)
                    f.setsampwidth(self.sampwidth)
                else:  # close file
                    if f is not None:
                        f.close()
                        f = None
            else:  # frames
                if f is not None:
                    f.writeframes(v)
                else:
                    # TODO this error was hit twice, perhaps on a split
                    # this happens when a file is closed prior to frames stopping
                    # which happens on stop_recording, perhaps reorganize the code
                    # so the steam stops before the file closes
                    logging.warning("WavFileWriter: Frames dropped, no open file")

    def open_file(self, filename):
        self._q.put(filename)

    def close_file(self):
        self._q.put("")

    def write_frames(self, frames):
        self._q.put(frames)

    def stop(self):
        self._q.put(None)
        self.join()


class Mic(threading.Thread):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

        self.running = False

        self._rate = 256000
        self._format = pyaudio.paInt16
        self._channels = 1
        self._period_size = 25600  # 100 ms

        self._format_width = pyaudio.get_sample_size(self._format)

        self._wav_file_writer = WavFileWriter(
            self._channels, self._rate,
            pyaudio.get_sample_size(self._format))
        self._wav_file_writer.start()
        self._wav_file_open = False

    def run(self):
        self.running = True

        def audio_frame_callback(in_data, frame_count, time_info, status):
            if frame_count != self._period_size:
                logging.warning(
                    "audio_frame_callback dropped frames: {}".format(
                        (len(in_data), frame_count, time_info, status)))
            else:
                self._wav_file_writer.write_frames(in_data)
            return b"", pyaudio.paContinue

        interface = pyaudio.PyAudio()
        # TODO pull out
        device_index = 2
        info = interface.get_host_api_info_by_index(0)
        for i in range(info.get('deviceCount')):
            dev_info = interface.get_device_info_by_host_api_device_index(0, i)
            if dev_info.get('maxInputChannels') < 1:
                continue
            if 'Pettersson' in dev_info['name']:  # TODO configure
                device_index = i
                break
        pcm = None

        while self.running:
            with self.lock:
                if self._wav_file_open:
                    if pcm is None:
                        # mic has not yet been opened, open mic
                        pcm = interface.open(
                            input_device_index=device_index,
                            format=self._format,
                            channels=self._channels,
                            rate=self._rate,
                            frames_per_buffer=self._period_size,
                            input=True,
                            stream_callback=audio_frame_callback)
                        pcm.start_stream()
                else:  # wav_file is closed
                    if pcm is not None:
                        pcm.stop_stream()
                        pcm.close()
                        pcm = None
                        self._wav_file_writer.close_file()
            time.sleep(0.001)

        interface.terminate()

    def start_recording(self, filename):
        logging.debug("Mic start_recording")
        with self.lock:
            self._wav_file_writer.open_file(filename)
            self._wav_file_open = True

    def split_recording(self, filename):
        logging.debug("Mic split_recording")
        with self.lock:
            #self._wav_file_writer.close_file()
            self._wav_file_writer.open_file(filename)
            self._wav_file_open = True

    def stop_recording(self):
        logging.debug("Mic stop_recording")
        with self.lock:
            #self._wav_file_writer.close_file()
            self._wav_file_open = False

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
            os.path.splitext(self.filename)[0] + '.wav')

    def split_recording(self):
        super().split_recording()
        self.mic.split_recording(
            os.path.splitext(self.filename)[0] + '.wav')

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
    backend.register(
        sysctl.SystemControl, r'^/system/.??')
    backend.register(
        filesystem.FileSystem, r'^/filesystem/.??')
    backend.serve(*args, **kwargs)
