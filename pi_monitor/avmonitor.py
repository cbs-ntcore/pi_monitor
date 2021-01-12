"""
Web server running on a pi with a camera and microphone
"""

import logging
import os
import re
import threading
import time
import wave

import alsaaudio

from . import backend
from . import camera
from . import filesystem
from . import mic
from . import sysctl


class Mic(threading.Thread):
    def __init__(self):
        super().__init__()
        self.lock = threading.Lock()

        self.running = False

        self._wav_file = None
        self._pcm = None

        self._device = 'dsnoop:CARD=Ultrasound,DEV=0'
        self._rate = 256000
        self._format = alsaaudio.PCM_FORMAT_S16_LE
        self._channels = 1
        self._period_size = 2048

        self._format_width = 2

    def run(self):
        self.running = True

        # compute delay time to wait 1/2 buffer
        buffer_delay_s = self._period_size / self._rate

        while self.running:
            # by default, wait 1 ms
            delay_s = 0.001
            with self.lock:
                if self._wav_file is not None:
                    if self._pcm is None:
                        # mic has not yet been opened, open mic
                        self._pcm = alsaaudio.PCM(
                            type=alsaaudio.PCM_CAPTURE, device=self._device)
                        self._pcm.setrate(self._rate)
                        self._pcm.setformat(self._format)
                        self._pcm.setchannels(self._channels)
                        self._pcm.setperiodsize(self._period_size)
                    n, bs = self._pcm.read()
                    if n > 0:
                        self._wav_file.writeframes(bs)
                    elif n < 0:  # dropped frames
                        logging.error(f"Dropped audio frames {n}")
                    # x.read will block up to 1 buffer so wait half that
                    # to allow functions outside thread to modify state
                    delay_s = buffer_delay_s
                else:  # wav_file is None
                    # file is None/closed, close mic
                    if self._pcm is not None:
                        self._pcm.close()
                        self._pcm = None
            time.sleep(delay_s)

        self.interface.terminate()

    def _open_wav_file(self, filename):
        """Do not call this without first acquiring the lock"""
        self._wav_file = wave.open(filename, 'wb')
        self._wav_file.setnchannels(self._channels)
        self._wav_file.setframerate(self._rate)
        self._wav_file.setsampwidth(self._format_width)

    def start_recording(self, filename):
        with self.lock:
            self._open_wav_file(filename)

    def split_recording(self, filename):
        with self.lock:
            self._wav_file.close()
            self._open_wav_file(filename)

    def stop_recording(self):
        with self.lock:
            self._wav_file.close()
            self._wav_file = None

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
