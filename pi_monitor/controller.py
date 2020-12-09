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

import requests

from . import server
from . import sysctl


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
        self.call_method("current_frame", "camera")

    def get_config(self):
        self.call_method("get_config", "camera")

    def set_config(self, *args, **kwargs):
        self.call_method("set_config", "camera", args=args, kwargs=kwargs)

    def get_disk_space(self, *args, **kwargs):
        self.call_method("get_disk_space", "filesystem", args=args, kwargs=kwargs)

    # TODO get file info, get individual files [through static files]


class Controller:
    def __init__(self):
        self.registered_monitors = set()
        # TODO load previously connected monitors from file on disk

    def add_monitor(self, ip, port=server.default_port):
        # register new monitor to server with new endpoint
        last_ip_digit = ip.split('.')[-1]
        if last_ip_digit in self.registered_monitors:
            return
        backend.register(
            MonitorConnection, r'^/monitor{}/.??'.format(last_ip_digit),
            args=(ip, port))
        self.registered_monitors.add(last_ip_digit)
        # TODO a way to unregister?


def run(*args, **kwargs):
    backend.register(Controller, r'^/controller/.??')
    backend.serve(*args, **kwargs)
