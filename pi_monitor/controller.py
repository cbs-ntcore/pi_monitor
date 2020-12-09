"""
Web server connected to multiple monitors (see monitor.py)
Features
- add/remove monitor
- for each monitor:
    - link to monitor site [only works for some networks]
    - live image
    - record/stop
    - start/stop streaming
    - get/convert/delete videos [and other files]
    - see free space and videos
    - set duration of recording [possibly all settings or leave that to monitor site?]
    - recent/current error message(s)
- for all monitors:
    - record/stop
    - convert [all]
    - transfer [all]
    - synchronize date [automatic]
    - start/stop streaming
"""

import datetime
import os

import requests

from . import backend
from . import config
from . import server
from . import sysctl


default_monitors = {
    'monitors': [
        '192.168.86.2.1',
        # ('192.168.86.2.1', 8000),  # can also be (ip, port) tuple
    ]
}

monitors_filename = os.path.expanduser('~/.pi_monitor/config/monitors.json')


def ip_to_pattern(ip):
    return r'^/monitor{}/.??'.format(ip.split('.')[-1])


class MonitorConnection:
    def __init__(self, ip, port=server.default_port):
        self.ip = ip
        self.port = port
        self.session = requests.Session()

    def link_url(self):
        return "http://{}:{}/monitor.html".format(self.ip, self.port)

    def call_method(self, method, endpoint, args=None, kwargs=None):
        url = "http://{}:{}/{}/".format(self.ip, self.port, endpoint.strip('/'))
        msg = {'method': method}
        if args is not None:
            msg['args'] = args
        if kwargs is not None:
            msg['kwargs'] = kwargs
        r = self.session.post(url, json=msg)
        if r.status_code != 200:
            raise Exception(
                "call_method on url {} failed with status_code {}".format(
                    url, r.status_code)) 
        response = r.json()
        if response.get('type', 'error') == 'error':
            raise Exception(
                "call_method on url {} failed with error {}".format(
                    url, response.get('error', None)))
        return response['result']

    def sync_date(self):
        dts = sysctl.date_formatted_datetime()
        self.call_method("set_date", "system", args=(dts, ))

    def current_frame(self):
        return self.call_method("current_frame", "camera")

    def get_config(self):
        return self.call_method("get_config", "camera")

    def set_config(self, *args, **kwargs):
        self.call_method("set_config", "camera", args=args, kwargs=kwargs)

    def get_disk_space(self, *args, **kwargs):
        return self.call_method("get_disk_space", "filesystem", args=args, kwargs=kwargs)

    # TODO get file info, get individual files [through static files]


class Controller:
    def __init__(self, monitors):
        self.monitors = monitors  # list of (ip, port)
    
    # TODO transfer files from monitor(s) to controller


def run(*args, **kwargs):
    # read list of monitors from config file
    monitors_cfg = config.load(monitors_filename, default_monitors)
    if 'monitors' not in monitors_cfg:
        raise Exception(
            f"Monitors list in {monitors_filename} missing 'monitors': {monitors_cfg}")
    monitors = []
    for m in monitors_cfg['monitors']:
        if isinstance(m, str):
            ip = m
            port = server.default_port
        else:
            assert len(m) == 2
            assert isinstance(m[0], str)
            assert isinstance(m[1], int)
            ip, port = m
        monitors.append((ip, port))
        backend.register(MonitorConnection, ip_to_pattern(ip), args=(ip, port))
    backend.register(Controller, r'^/controller/.??', args=(monitors, ))
    backend.serve(*args, **kwargs)
