import datetime
import logging
import os
import re
import socket
import threading
import time
import wave

import pyaudio

from . import backend
from . import config


default_config = {
    'device_name': 'Pettersson',
    'rate': 256000,
    'nchannels': 1,
    'duration_s': 3600 * 24,  # or 0 to disable
    'filename': '{host}_{date}_{time}_{index}.wav',
    'split_duration_s': 3600,
    'save_directory': '/home/pi/audio',
}

config_filename = os.path.expanduser('~/.pi_monitor/config/mic.json')
hostname = socket.gethostname()


class MicThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = False
        self.record_start = None
        self.filename_index = 0
        self.chunk_count = 0
        self.filename = None

        self.lock = threading.Lock()

        self.cfg = config.load(config_filename, default_config)

    def static_directory(self):
        with self.lock:
            self.cfg['save_directory']

    def is_recording(self):
        with self.lock:
            return self.record_start is not None

    def run(self):
        self.running = True
        try:
            self.interface = pyaudio.PyAudio()
        except Exception as e:
            logging.error("Failed to open audio interface: {e}")
            self.running = False
            return

        while self.running:
            action = 'wait'
            with self.lock:
                if self.record_start is not None:  # is recording
                    # wait for next chunk and write it
                    bs = self.stream.read(self.cfg['rate'])
                    self.wav_file.writeframes(bs)
                    self.chunk_count += 1
                    # split recording?
                    if self.chunk_count % self.cfg['split_duration_s'] == 0:
                        action = 'split'
                    else:
                        action = 'pass'
                    if self.chunk_count >= self.cfg['duration_s']:
                        action = 'stop'
                # else do nothing
            if action == 'wait':
                time.sleep(0.001)
            elif action == 'split':
                self.split_recording()
            elif action == 'stop':
                self.stop_recording()
        self.interface.terminate()

    def stop(self):
        with self.lock:
            self.running = False
        self.join()

    def set_config(self, cfg, update=False, save=False):
        delta = {}
        with self.lock:
            pcfg = copy.deepcopy(self.cfg)
            if update:
                logging.debug("set_config: update with: {}".format(cfg))
                self.cfg.update(cfg)
            else:
                logging.debug("set_config: replace with: {}".format(cfg))
                self.cfg = cfg

            # look for config changes
            for k in self.cfg:
                if self.cfg[k] != pcfg.get(k, {}):
                    delta[k] = self.cfg[k]
            logging.debug("set_config: delta: {}".format(delta))

            if save:
                to_save = copy.deepcopy(self.cfg)

        if 'record' in delta:
            if delta['record']:
                self.start_recording()
            else:
                self.stop_recording()

        if save:
            logging.debug(f"Saving config to {config_filename}")
            config.save(to_save, config_filename)

    def get_config(self):
        with self.lock:
            return copy.deepcopy(self.cfg)

    def next_filename(self):
        with self.lock:
            if self.record_start is None:
                self.filename_index = 0
            # %d : day as YYMMDD
            # %t : time as HHMMSS
            # %h : hostname
            # %i : filename index
            dt = datetime.datetime.now()
            tokens = {
                'index': self.filename_index,
                'host': hostname,
                'date': dt.strftime('%y%m%d'),
                'time': dt.strftime('%H%M%S'),
            }
            fn = self.cfg['filename'].format(**tokens)
            self.filename_index += 1
            self.filename = os.path.join(self.cfg['save_directory'], fn)

            # make directory if it doesn't exist
            directory = os.path.dirname(self.filename)
            if not os.path.exists(directory) and directory != '':
                logging.debug(f"Making directory {directory}")
                os.makedirs(directory)
            return self.filename

    def start_recording(self):
        fn = self.next_filename()
        with self.lock:
            rate = self.cfg['rate']
            channels = self.cfg['nchannels']
            sample_format = pyaudio.paInt16  # TODO read from device
            input_device_index = self._find_device_index(self.cfg['device_name'])

            self.stream = self.interface.open(
                input_device_index=input_device_index,
                format=sample_format,
                channels=channels,
                rate=rate,
                frames_per_buffer=rate,  # always chunk 1 second
                input=True)

            self.wav_file = wave.open(fn, 'wb')
            self.wav_file.setnchannels(channels)
            self.wav_file.setsampwidth(pyaudio.get_sample_size(sample_format))
            self.wav_file.setframerate(rate)

            self.record_start = time.monotonic()
            self.cfg['record'] = True

    def split_recording(self):
        # TODO only if recording?
        # TODO can I split within a chunk?
        fn = self.next_filename()
        with self.lock:
            # close current wave file
            channels = self.wav_file.getnchannels()
            samp_width = self.wav_file.getsampwidth()
            rate = self.wav_file.getframerate()
            self.wav_file.close()

            # open next one
            self.wav_file = wave.open(fn, 'wb')
            self.wav_file.setnchannels(channels)
            self.wav_file.setsampwidth(samp_width)
            self.wav_file.setframerate(rate)

    def stop_recording(self):
        with self.lock:
            if self.record_start is None:
                return
            # close current stream
            self.stream.stop_stream()
            self.stream.close()
            # close current wave file
            self.wav_file.close()
            self.record_start = None
            self.cfg['record'] = False

    def _find_device_index(self, name_pattern):
        info = self.interface.get_host_api_info_by_index(0)
        numdevices = info.get('deviceCount')

        for i in range(numdevices):
            dev_info = self.interface.get_device_info_by_host_api_device_index(0, i)
            if dev_info.get('maxInputChannels') > 0:
                name = dev_info.get('name')
                if re.match(name_pattern, name):
                    return i
        raise Exception(f"No device found with name {name}")


def run(*args, **kwargs):
    backend.register(
        MicThread, r'^/mic/.*',
        init=lambda o: o.start(), deinit=lambda o: o.stop())
    backend.serve(*args, **kwargs)

