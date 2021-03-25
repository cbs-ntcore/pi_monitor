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
import ipaddress
import logging
import os
import subprocess
import threading

import requests

from . import backend
from . import config
from . import filesystem
from . import server
from . import sysctl


default_monitors = {
    "monitors": [
        #"192.168.2.1",
        # ("192.168.2.1", 8000),  # can also be (ip, port) tuple
    ]
}

monitors_filename = os.path.expanduser("~/.pi_monitor/config/monitors.json")
# TODO move this into the config file and make it dynamic
videos_directory = os.path.expanduser("~/videos")


def ip_to_index(ip):
    return int(ip.split(".")[-1])


def ip_to_pattern(ip):
    return r"^/monitor{}/.??".format(ip_to_index(ip))


class MonitorConnection:
    def __init__(self, ip, port=server.default_port):
        logging.debug(f"MonitorConnection __init__ for {ip}:{port}")
        self.ip = ip
        self.name = "monitor{}".format(ip_to_index(ip))
        self.port = port
        self.session = requests.Session()
        self.transfer_process = None

    def link_url(self):
        return "http://{}:{}/monitor.html".format(self.ip, self.port)

    def call_method(self, method, endpoint, args=None, kwargs=None):
        url = "http://{}:{}/{}/".format(self.ip, self.port, endpoint.strip("/"))
        msg = {"method": method}
        if args is not None:
            msg["args"] = args
        if kwargs is not None:
            msg["kwargs"] = kwargs
        r = self.session.post(url, json=msg)
        if r.status_code != 200:
            raise Exception(
                "call_method on url {} failed with status_code {}".format(
                    url, r.status_code)) 
        response = r.json()
        if response.get("type", "error") == "error":
            raise Exception(
                "call_method on url {} failed with error {}".format(
                    url, response.get("error", None)))
        return response["result"]

    def sync_date(self):
        dts = sysctl.date_formatted_datetime()
        self.call_method("set_date", "system", args=(dts, ))

    def current_frame(self):
        return self.call_method("current_frame", "camera")

    def start_recording(self):
        return self.call_method(
            "set_config", "camera",
            args=({"record": True}, ), kwargs={"update": True})

    def stop_recording(self):
        return self.call_method(
            "set_config", "camera",
            args=({"record": False}, ), kwargs={"update": True})

    def toggle_recording(self):
        cfg = self.get_config()
        if cfg['record']:
            return self.stop_recording()
        else:
            return self.start_recording()

    def get_config(self):
        return self.call_method("get_config", "camera")

    def set_config(self, *args, **kwargs):
        self.call_method("set_config", "camera", args=args, kwargs=kwargs)

    def get_disk_space(self, *args, **kwargs):
        return self.call_method("get_disk_space", "filesystem", args=args, kwargs=kwargs)

    def convert_all_files(self, directory=None):
        if directory is None:
            cfg = self.get_config()
            directory = cfg["video_directory"]
        cfg = self.get_config()
        return self.call_method(
            "convert_all_files", "filesystem", args=(directory, ))

    def is_converting(self):
        return self.call_method("is_converting", "filesystem")

    def get_state(self, directory=None):
        if directory is None:
            cfg = self.get_config()
            directory = cfg["video_directory"]
        bytes_free = self.get_disk_space(directory)
        return {
            "recording": cfg["record"],
            "disk_space": bytes_free,
            "converting": self.is_converting(),
        }

    def get_file_info(self, directory=None):
        if directory is None:
            cfg = self.get_config()
            directory = cfg["video_directory"]
        file_info = self.call_method(
            "get_file_info", "filesystem", args=(directory, ))
        return file_info
    
    def is_transferring(self):
        return (
            self.transfer_process is not None and
            self.transfer_process.poll() is None)

    def transfer_files(self, destination_directory):
        if self.transfer_process is not None and self.transfer_process.poll() is None:
            raise Exception("Transfer already in progress, only 1 allowed")

        # first fetch monitor (src) video directory
        source_directory = self.get_config()["video_directory"]

        # don't transfer open files
        fns = []
        for fi in self.get_file_info(source_directory):
            if fi['open']:
                continue
            name = fi['name']
            # TODO filter by name/extension
            fns.append(name)
        cmd = [
            "rsync",
            "-u",
            "--files-from=-",
            f"{self.ip}:{source_directory}",
            f"{destination_directory}",
        ]
        self.transfer_process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE)
        #self.transfer_process.communicate(input="\n".join(fns))
        #self.transfer_process.stdin.write("\n".join(fns).encode())

        # setup thread to watch process until it finishes
        def check_transfer_process(proc, fns):
            proc.communicate(input="\n".join(fns).encode())
            while proc.poll() is None:
                outs, errs = proc.communicate()

        self.transfer_thread = threading.Thread(
            target=check_transfer_process, args=(self.transfer_process, fns)).start()


class Controller:
    def __init__(self, monitor_info):
        self.monitor_info = monitor_info  # list of (ip, port)
        self.monitors = [MonitorConnection(*i) for i in self.monitor_info]
    
    def get_monitors(self):
        return self.monitor_info

    def start_recording(self):
        [m.start_recording() for m in self.monitors]

    def stop_recording(self):
        [m.stop_recording() for m in self.monitors]

    def convert_all_files(self):
        [m.convert_all_files() for m in self.monitors]

    def is_converting(self):
        return any((m.is_converting() for m in self.monitors))

    def is_transferring(self):
        return any((m.is_transferring() for m in self.monitors))

    def transfer_files(self, destination_directory):
        for monitor in self.monitors:
            monitor_dst = os.path.join(destination_directory, monitor.name)
            if not os.path.exists(monitor_dst):
                os.makedirs(monitor_dst)
            monitor.transfer_files(monitor_dst)


def run(*args, **kwargs):
    # read list of monitors from config file
    monitors_cfg = config.load(monitors_filename, default_monitors)
    if "monitors" not in monitors_cfg:
        raise Exception(
            f"Monitors list in {monitors_filename} missing 'monitors': {monitors_cfg}")
    monitors = []
    for m in monitors_cfg["monitors"]:
        if isinstance(m, str):
            ip = m
            port = server.default_port
        else:
            assert len(m) == 2
            assert isinstance(m[0], str)
            assert isinstance(m[1], int)
            ip, port = m
        monitors.append((ip, port))
        backend.register(MonitorConnection, ip_to_pattern(ip), ip, args=(ip, port))
    backend.register(Controller, r"^/controller/.??", args=(monitors, ))
    backend.register(filesystem.FileSystem, r"^/filesystem/.??")
    backend.serve(*args, **kwargs)


def cmdline_configure():
    if os.path.exists(monitors_filename):
        print(f"Found existing monitors.json at {monitors_filename}")
        try:
            monitors = config.load(monitors_filename, default_monitors)
        except Exception as e:
            print(f"Error while loading {monitors_filename}: {e}")
            print("using default monitors")
            monitors = default_monitors
    while True:
        print("Current monitors:")
        for m in sorted(monitors['monitors']):
            print(f"\t{m}")
        print("Would you like to [a]dd, [d]elete, [s]ave or [q]uit?")
        r = input(">>").lower().strip()
        if len(r) == 0:
            print(f"Invalid input: '{r}' is 0 length")
            continue
        if r[0] == 'q':  # quit
            print("Quitting...")
            break
        elif r[0] == 's':  # save
            print(f"Saving to {monitors_filename}")
            try:
                config.save(monitors, monitors_filename)
                print("Finished saving")
            except Exception as e:
                print(f"!! Failed to save with exception {e} !!")
        elif r[0] == 'd':  # remove
            print("Enter the ip address you want to remove")
            ip = input(">>").strip()
            if ip not in monitors['monitors']:
                print(f"Invalid ip {ip} not in list")
            else:
                monitors['monitors'].remove(ip)
        elif r[0] == 'a':  # add
            print("Enter the ip address you want to add")
            ip = input(">>").strip()
            # TODO check this is a valid ip
            try:
                ipaddress.ip_address(ip)
            except ValueError as e:
                print(f"ip {ip} is invalid: {e}")
                continue
            if ip in monitors['monitors']:
                print(f"ip {ip} already in monitors")
            else:
                print(f"Adding ip {ip} to monitors")
                monitors['monitors'].append(ip)
        else:
            print(f"Unknown input {r}")
