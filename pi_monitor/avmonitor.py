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

import alsaaudio

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
                    f.close()
                    f = None
            else:  # frames
                f.writeframes(v)

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

        self._pcm = None

        self._device = 'dsnoop:CARD=Ultrasound,DEV=0'
        self._rate = 256000
        self._format = alsaaudio.PCM_FORMAT_S16_LE
        self._channels = 1
        self._period_size = 25600  # 100 ms

        self._format_width = 2

        self._wav_file_writer = WavFileWriter(
            self._channels, self._rate, self._format_width)
        self._wav_file_writer.start()
        self._wav_file_open = False

    def run(self):
        self.running = True

        # compute delay time to wait 1/2 buffer
        buffer_delay_s = self._period_size / self._rate

        while self.running:
            # by default, wait 1 ms
            delay_s = 0.001
            with self.lock:
                if self._wav_file_open:
                    if self._pcm is None:
                        # mic has not yet been opened, open mic
                        logging.debug("Mic opening device %s", self._device)
                        self._pcm = alsaaudio.PCM(
                            type=alsaaudio.PCM_CAPTURE, device=self._device)
                        self._pcm.setrate(self._rate)
                        self._pcm.setformat(self._format)
                        self._pcm.setchannels(self._channels)
                        self._pcm.setperiodsize(self._period_size)
                    n, bs = self._pcm.read()
                    if n > 0:
                        self._wav_file_writer.write_frames(bs)
                    elif n < 0:  # dropped frames
                        logging.error(f"Dropped audio frames {n}")
                    # x.read will block up to 1 buffer so wait half that
                    # to allow functions outside thread to modify state
                    #delay_s = buffer_delay_s
                else:  # wav_file is closed
                    # file is None/closed, close mic
                    if self._pcm is not None:
                        logging.debug("Mic closing device %s", self._device)
                        self._pcm.close()
                        self._pcm = None
            time.sleep(delay_s)

        self.interface.terminate()

    def start_recording(self, filename):
        logging.debug("Mic start_recording")
        with self.lock:
            self._wav_file_writer.open_file(filename)
            self._wav_file_open = True

    def split_recording(self, filename):
        logging.debug("Mic split_recording")
        with self.lock:
            self._wav_file_writer.close_file()
            self._wav_file_writer.open_file(filename)
            self._wav_file_open = True

    def stop_recording(self):
        logging.debug("Mic stop_recording")
        with self.lock:
            self._wav_file_writer.close_file()
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
