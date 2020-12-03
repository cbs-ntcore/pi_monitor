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
    'stream_period': 1000,  # update 'stream' image every N ms
    'record': False,  # start/stop recording
    # see get_next_filename for formatting
    'filename': '{host}_{date}_{time}_{index}.h264',
    'split_duration_ms': 0,  # split video every N ms
    'duration_ms': 1000 * 60 * 60,  # or 0 for continuous recording
    'settings': {},  # direct camera settings
    'video_directory': '/home/pi/videos/',
    'timestamp_period_ms': 30000, # or 0 to disable
}


class SettingConverter:
    def __init__(self, vtype=None, limit=None):
        if vtype is None:
            self.force_type = lambda v: v
        else:
            self.force_type = lambda v, vtype=vtype: vtype(v)
        if limit is None:
            self.check_limit = lambda v: True
        elif isinstance(limit, dict):
            self.check_limit = lambda v, limit=limit: (v in limit) or (v in limit.values())
        elif isinstance(limit, set):
            self.check_limit = lambda v, limit=limit: v in limit
        elif isinstance(limit, (tuple, list)):
            assert len(limit) == 2, f"SettingConverter limit[{limit}] not 2 length"
            self.check_limit = lambda v, low=limit[0], high=limi[1]: (v >=low) and (v <= high)

    def to_picamera(self, value):
        value = self.force_type(value)
        if self.check_limit(value):
            raise ValueError(
                "SettingConverter: value {} out of limit {}".format(
                    value, self.limit))
        return value
    
    def to_cfg(self, value):
        return value


class FractionConverter:
    def to_picamera(self, value):
        if len(value) == 1:
            return (value, 1)
        elif len(value) == 2:
            return value
        raise ValueError("Invalid Fraction value: {}".format(value))
    
    def to_cfg(self, value):
        return [value.numerator, value.denominator]


all_settings = {
    #'analog_gain',  # fraction:  read only
    #'awb_gains',  # (fraction, fraction): color adjustment
    'awb_mode': SettingsConverter(),  # str: should be in AWB_MODES
    'brightness': SettingsConverter(vtype=int, limit=(0, 100)),  # int: [0-100]
    'clock_mode': SettingsConverter(),  # str: must be in CLOCK_MODES
    'contrast': SettingsConverter(vtype=int, limit=(-100, 100)),  # int: [-100-100]
    #'crop',  # (float, float, float, float) {depreciated, use zoom}
    'digital_gain': FractionConverter(),  # fraction
    'drc_strength': SettingsConverter(),  # str: must be in DRC_STRENGTHS
    #'exif_tags',  # dict: only used in jpeg saving
    'exposure_compensation': SettingsConverter(vtype=int, limit=(-25, 25)),  # int: [-25-25]
    'exposure_mode': SettingsConverter(),  # str: must be in EXPOSURE_MODES
    'flash_mode': SettingsConverter(),  # str: must be in FLASH_MODES
    'framerate': FractionConverter(),  # fraction: target framerate
    #'framerate_delta',  # fraction: fine tune framerate [reset when framerate set]
    #'framerate_range',  # (fraction, fraction): allow framerate to drift over range
    'hflip': SettingsConverter(vtype=bool),  # bool
    #'image_denoise',  # bool only used for image capture
    'iso': SettingsConverter(vtype=int, limit=(0, 1600)),  # int: [0-1600] 0=auto
    'meter_mode': SettingsConverter(),  # str: must be in METER_MODES
    'resolution': SettingsConverter(),  # (int, int) or str: must not be recording when set
    #'revision',  # str?
    'rotation': SettingsConverter(limit={0, 90, 180, 270}),  # int: must be in [0, 90, 180, 270]
    'saturation': SettingsConverter(limit=(-100, 100)),  # int: [-100-100]
    'sensor_mode': SettingsConverter(vtype=int),  # int: 0 = auto
    'sharpness': SettingsConverter(vtype=int, limit=(-100, 100)),  # int: [-100-100]
    'shutter_speed': SettingsConverter(vtype=int),  # int: 0=auto, other=microseconds
    'vflip': SettingsConverter(vtype=bool),  # bool
    'video_denoise': SettingsConverter(vtype=bool),  # bool
    'video_stabilization': SettingsConverter(vtype=bool),  # bool
    'zoom': SettingsConverter(),  # (float, float, float, float): (x, y, w, h) all 0-1
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
        self.cfg['record'] = False

    def static_directory(self):
        with self.lock:
            return self.cfg['video_directory']

    def is_recording(self):
        with self.lock:
            return self.record_start is not None

    def _set_camera_settings(self):
        # for camera 'settings' (fps etc) the default and loaded config might differ
        # the loaded settings should take precedence. However, some settings might
        # be rounded by the camera so after setting, get all the settings to have
        # the correct current settings
        settings = self.cfg['settings']
        for k in settings:
            if k in all_settings:
                try:
                    v = all_settings[k].to_picamera(settings[k])
                except Exception as e:
                    logging.error(f"Failed to convert setting to_picamera {k}: {e}")
                    v = settings[k]
            else:
                v = settings[k]
            try:
                setattr(self.cam, k, v)
            except Exception as e:
                logging.error(f"Failed to set setting {k} to {v}: {e}")
        for k in set(settings).union(set(all_settings)):
            v = getattr(self.cam, k)
            if k in all_settings:
                try:
                    v = all_settings[k].to_cfg(v)
                except Exception as e:
                    logging.error(f"Failed to convert setting to_cfg {k}: {e}")
                    v = None  # set to safe, unknown value
            settings[k] = v
        self.cfg['settings'] = settings

    def run(self):
        self.running = True
        self.cam = PiCamera()
        with self.lock:
            self._set_camera_settings()
            #for s in self.cfg['settings']:
            #    setattr(self.cam, s, self.cfg['settings'][s])
            ## fetch initial settings
            #for s in all_settings:
            #    if s in self.cfg['settings']:
            #        continue
            #    self.cfg['settings'][s] = getattr(self.cam, s)
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

            if 'settings' in delta:
                logging.debug("set_config: contains settings: {}".format(delta['settings']))
                self._set_camera_settings()
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

    def current_frame(self):
        f = io.BytesIO()
        with self.lock:
            self.cam.capture(
                f, 'jpeg', use_video_port=True, resize=self.cfg['stream_resolution'])
        f.seek(0)
        return base64.b64encode(f.read()).decode('ascii')

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
            self.filename = os.path.join(self.cfg['video_directory'], fn)

            # make directory if it doesn't exist
            directory = os.path.dirname(self.filename)
            if not os.path.exists(directory) and directory != '':
                logging.debug(f"Making directory {directory}")
                os.makedirs(directory)
            return self.filename

    def _write_timestamp(self, t=None):
        frame = self.cam.frame
        if frame.timestamp is None:
            # sometimes timestamp will be None
            # return without writing timestamp to allow for retry
            return False
        fn = os.path.splitext(self.filename)[0] + '.txt'
        with open(fn, 'a') as f:
            f.write("{},{}\n".format(frame.index, frame.timestamp))
        if t is None:
            t = time.monotonic()
        self.last_timestamp = t
        return True

    def start_recording(self):
        fn = self.next_filename()
        with self.lock:
            self.cam.start_recording(fn, 'h264', inline_headers=True)
            self.record_start = time.monotonic()
            self.last_split = self.record_start
            self.cfg['record'] = True
            if self.cfg['timestamp_period_ms'] != 0:
                retries = 0
                while not self._write_timestamp():
                    self.cam.wait_recording(0.001)
                    retries += 1
                    if retries > 100:
                        raise Exception("Failed to write frame timestamp")

    def split_recording(self):
        fn = self.next_filename()
        with self.lock:
            self.cam.split_recording(fn)
            self.last_split = time.monotonic()

    def stop_recording(self):
        with self.lock:
            if self.record_start is None:
                return
            if self.cfg['timestamp_period_ms'] != 0:
                retries = 0
                self._write_timestamp()
                while not self._write_timestamp():
                    self.cam.wait_recording(0.001)
                    retries += 1
                    if retries > 10:
                        logging.error("Failed to write last timestamp")
                        break
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
    ncfg['filename'] = '{index}_{index}.h264'
    ncfg['video_directory'] = ''
    cam.set_config(ncfg, update=False)
    # check that config updates
    assert cam.get_config() == ncfg

    # check filename formatting
    with cam.lock:
        # fake recording so filename index doesn't reset
        cam.record_start = 0
    for tfn in ('0_0.h264', '1_1.h264'):
        fn = cam.next_filename()
        assert fn == tfn, f"{fn} != {tfn}"
    cam.set_config({"filename": "{index:04d}_{index:02d}.h264"}, update=True)
    for tfn in ('0002_02.h264', '0003_03.h264'):
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
                'filename': '{host}_{date}_{time}_{index}.h264',
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
