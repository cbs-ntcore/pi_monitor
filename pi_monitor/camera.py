"""
Wrapper for picamera that allow:
- adjusting settings from config structure
- saving to file (possibly segmented/sequence)
- streaming (get most recent frame base64 encoded)

Also a 'mock' class to allow testing on a non-pi system
"""
import base64
import copy
import datetime
import io
import logging
import os
import socket
import tempfile
import threading
import time

try:
    if os.environ.get("PM_FAKE_PICAMERA", 0):
        raise ImportError
    import picamera
    from picamera import PiCamera
except ImportError:
    from .mockpicamera import PiCamera

from . import backend
from . import config


default_config = {
    'stream_resolution': (320, 240),  # stream/current_frame resolution
    'record': False,  # start/stop recording
    'filename': '%h_%d_%t_%i.h264',  # see get_next_filename for formatting
    'split_duration_ms': 0,  # split video every N ms
    'duration_ms': 1000 * 60 * 60,  # or 0 for continuous recording
    'settings': {},  # direct camera settings
    'video_directory': '/home/pi/videos/',
    'timestamp_period_ms': 30000, # or 0 to disable
}

config_filename = os.path.expanduser('~/.pi_monitor/config/camera.json')
hostname = socket.gethostname()


class CameraThread(threading.Thread):
    def __init__(self):
        super().__init__()
        self.running = False
        self.record_start = None
        self.last_split = None
        self.last_timestamp = None
        self.filename_index = 0
        self.filename = None

        self.lock = threading.Lock()
        self.cfg = config.load(config_filename, default_config)

    def run(self):
        self.running = True
        self.cam = PiCamera()
        while self.running:
            action = 'wait'
            with self.lock:
                if self.record_start is not None:  # is recording
                    # check duration and split against time.monotonic
                    t = time.monotonic()
                    dt = t - self.record_start
                    duration = self.cfg['duration_ms']
                    if duration != 0:  # time limited
                        duration /= 1000  # convert to ms
                        if dt > duration:
                            action = 'stop'
                    split_duration = self.cfg['split_duration_ms']
                    if action != 'stop' and split_duration != 0:  # split
                        if t - self.last_split > split_duration / 1000:
                            action = 'split'
                    timestamp_period_ms = self.cfg['timestamp_period_ms']
                    if (
                            timestamp_period_ms != 0 and
                            t - self.last_timestamp > timestamp_period_ms / 1000):
                        self._write_timestamp(t)
                    if action == 'wait':
                        self.cam.wait_recording(0.001)
                        action = None
            if action == 'wait':
                time.sleep(0.001)
            elif action == 'split':
                self.split_recording()
            elif action == 'stop':
                self.stop_recording()
            else:
                pass

    def stop(self):
        with self.lock:
            self.running = False
        self.join()

    def set_config(self, cfg, update=False):
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

            if 'settings' in delta:
                logging.debug("set_config: contains settings: {}".format(delta['settings']))
                for k in delta['settings']:
                    setattr(self.cam, k, delta['settings'][k])

        if 'record' in delta:
            if delta['record']:
                self.start_recording()
            else:
                self.stop_recording()

    def get_config(self):
        with self.lock:
            return copy.deepcopy(self.cfg)

    def current_frame(self):
        f = io.BytesIO()
        with self.lock:
            self.cam.capture(
                f, 'jpeg', use_video_port=True, resize=self.cfg['stream_resolution'])
        f.seek(0)
        return f.read()

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
                '%i': str(self.filename_index),  # TODO zero pad?
                '%h': hostname,
                '%d': dt.strftime('%y%m%d'),
                '%t': dt.strftime('%H%M%S'),
            }
            fn = self.cfg['filename']
            for token in tokens:
                if token in fn:
                    fn = fn.replace(token, tokens[token])
            # TODO check extension
            self.filename_index += 1
            self.filename = os.path.join(self.cfg['video_directory'], fn)
            return self.filename

    def _write_timestamp(self, t=None):
        fn = os.path.splitext(self.filename)[0] + '.txt'
        frame = self.cam.frame
        with open(fn, 'a') as f:
            f.write("{},{}\n".format(frame.index, frame.timestamp))
        if t is None:
            t = time.monotonic()
        self.last_timestamp = t

    def start_recording(self):
        fn = self.next_filename()
        with self.lock:
            self.cam.start_recording(fn, 'h264', inline_headers=True)
            self.record_start = time.monotonic()
            self.last_split = self.record_start
            if self.cfg['timestamp_period_ms'] != 0:
                self._write_timestamp()
            self.cfg['record'] = True

    def split_recording(self):
        fn = self.next_filename()
        with self.lock:
            self.cam.split_recording(fn)
            self.last_split = time.monotonic()

    def stop_recording(self):
        with self.lock:
            if self.record_start is None:
                return
            self.cam.stop_recording()
            self.record_start = None
            self.last_split = None
            self.cfg['record'] = False


def run(*args, **kwargs):
    backend.register(
        CameraThread, r'^/camera/.*',
        init=lambda o: o.start(), deinit=lambda o: o.stop())
    backend.serve(*args, **kwargs)


def test():
    # force use of mock camera
    from .mockpicamera import PiCamera

    # create and start camera thread
    cam = CameraThread()
    cam.start()

    cfg = cam.get_config()
    ncfg = copy.deepcopy(default_config)
    ncfg['filename'] = '%i.h264'
    ncfg['video_directory'] = ''
    cam.set_config(ncfg, update=False)
    # check that config updates
    assert cam.get_config() == ncfg

    # check filename formatting
    with cam.lock:
        # fake recording so filename index doesn't reset
        cam.record_start = 0
    for tfn in ('0.h264', '1.h264'):
        fn = cam.next_filename()
        assert fn == tfn, f"{fn} != {tfn}"
    with cam.lock:
        # undo fake recording
        cam.record_start = None

    # check that config updating works
    cam.set_config({'filename': 'test'}, update=True)
    assert cam.get_config()['filename'] == 'test'
    assert cam.get_config()['stream_resolution'] == ncfg['stream_resolution']
    # reset config
    cam.set_config(cfg, update=False)

    for v in (30, 15):
        # set a setting
        cam.set_config({'settings': {'fps': v}}, update=True)
        # confirm it changed
        with cam.lock:
            assert cam.cam.fps == v, "{} != {}".format(cam.cam.fps, v)

    
    # setup to record a 1000 ms video split into 5 chunks
    with tempfile.TemporaryDirectory() as tdir:
        dt = datetime.datetime.now()
        t0 = time.monotonic()
        cam.set_config(
            {
                'video_directory': tdir,
                'duration_ms': 1000,
                'split_duration_ms': 200,
                'timestamp_period_ms': 100,
                'filename': '%h_%d_%t_%i.h264',
                'record': True},
            update=True)
        time.sleep(0.5)
        assert cam.get_config()['record']
        while cam.get_config()['record']:
            logging.debug("Waiting for record to finish...")
            if time.monotonic() - t0 > 3.0:
                raise Exception("Record failed to finish")
            time.sleep(0.25)
        with cam.lock:
            assert len(cam.cam.calls['start_recording']) == 1, (
                len(cam.cam.calls['start_recording']))
            assert len(cam.cam.calls['stop_recording']) == 1, (
                len(cam.cam.calls['stop_recording']))
            assert 5 > len(cam.cam.calls['split_recording']) > 3, (
                len(cam.cam.calls['split_recording']))
        # check temporary directory for timestamp file
        fns = os.listdir(tdir)
        assert 6 > len(fns) > 3, fns
        fn = sorted(fns)[0]
        
        # check timestamp filename format
        bfn = os.path.splitext(os.path.basename(fn))[0]
        tokens = bfn.split('_')
        assert len(tokens) == 4, tokens
        assert tokens[-1] == '0', tokens[-1]
        fdt = datetime.datetime.strptime('_'.join(tokens[1:3]), '%y%m%d_%H%M%S')
        if fdt > dt:
            ddt = fdt - dt
        else:
            ddt = dt - fdt
        assert ddt.seconds < 1, ddt
        with open(os.path.join(tdir, fn), 'r') as f:
            for (i, l) in enumerate(f):
                if len(l.strip()) == 0:
                    continue
                tokens = l.strip().split(',')
                assert len(tokens) == 2, (i, tokens)

    # stop camera thread
    cam.stop()
