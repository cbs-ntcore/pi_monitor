#!/usr/bin/env python3
"""
urls:
  / = index:
    show state (recording/not recording)
    grab image from camera (and display)
    show space left on disk
    show videos on disk (allow delete of videos)
  /camera (all post requests)
    grab: grab image (allow parameter setting)
    record: start recording (allow parameter setting)
    status: get recording status, disk space, available videos
    remove: remove video file
    config: set grab/record settings
    op: (grab/record/status/space/remove/config)

  configuration:
    (add hostname to video filename) [meh]
    (duration) [meh]
    (grab arguments) [meh]
    (night mode [getting LED control is tricky on the pi3])

  duration: allow ms/s/m/h & inf
"""

import datetime
import fcntl
import json
import os
import socket
import struct
import subprocess
import sys
import time
import urllib.parse

import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web


this_directory = os.path.dirname(os.path.realpath(__file__))
static_directory = os.path.join(this_directory, 'static')
video_directory = os.path.join(this_directory, 'videos')
grab_args_fn = os.path.expanduser('~/.grab_args')


def set_led(state, led=134):
    if state not in (0, 1):
        raise ValueError("Invalid state: %s (not 0/1)" % state)
    b = struct.pack("=8I", 32, 0, 0x38041, 8, 0, led, state, 0)
    f = os.open("/dev/vcio", os.O_TRUNC)
    try:
        fcntl.ioctl(f, 0xC0046400, b)
    except Exception as e:
        try:
            os.close(f)
        except Exception:
            pass
        raise e


class CamSite(tornado.web.RequestHandler):
    def get(self):
        template = os.path.join(this_directory, 'templates', 'camera.html')
        self.render(template)


class CamQuery(tornado.web.RequestHandler):
    def is_recording(self):
        if self.application.record_process is None:
            return False
        r = self.application.record_process.poll()
        if r is None:  # still recording
            return True
        # finished for some reason, save error
        self.error = r
        # TODO save stdout or more information?
        return False

    def return_image(self):
        # check if recording
        if self.is_recording():
            self.set_status(400)
            self.write("Bad Request: cannot grab image while recording")
            return
        cmd = " ".join(["raspistill -t 300 -n -o -", self.application.grab_args])
        print("calling: %s" % (cmd, ))
        try:
            r = subprocess.check_output(cmd.split())
        except subprocess.CalledProcessError as e:
            self.set_status(500)
            self.write("raspistill failed: %s" % (e, ))
            return
        self.set_header("Content-type", "image/jpeg")
        self.write(r)

    def get_disk_space(self):
        cmd = "df -h %s" % video_directory
        output = subprocess.check_output(cmd, shell=True).decode('latin8')
        lines = output.strip().split(os.linesep)
        l = lines[-1]
        ts = l.split()
        space, used, avail, perc = ts[1], ts[2], ts[3], ts[4]
        return avail

    def get_video_filenames(self):
        fns = [os.path.splitext(fn) for fn in os.listdir(video_directory)]
        return [fn[0] for fn in fns if fn[1] == '.h264']

    def get(self):
        self.return_image()
    
    def check_filename(self, fn):
        for c in '. \\/':
            if c in fn:
                return True
        return False

    def post(self):
        args = list(self.request.arguments.keys())
        kwargs = {k: self.get_argument(k) for k in args}
        if 'op' not in kwargs:
            self.set_status(400)  # bad request
            self.write("Bad Request: missing operation[op]")
            return
        op = kwargs['op']
        if op == 'grab':
            # grab camera frame return as jpeg
            self.return_image()
            return
        elif op == 'led':
            if 'state' not in kwargs:
                self.set_status(400)
                self.write("Bad Request: missing state [0/1]")
            try:
                set_led(int(kwargs['state']))
            except Exception as e:
                self.set_status(500)
                self.write(
                    "Server error: failed to set led to state=%s"
                    % kwargs['state'])
        elif op == 'record':
            # record video (if not recording)
            if self.is_recording():
                self.set_status(400)
                self.write("Bad Request: already recording")
                return
            # get filename from kwargs (or make a new one)
            if 'fn' in kwargs:
                fn = kwargs['fn']
                if self.check_filename(fn):
                    self.set_status(400)
                    self.write("Bad Request: invalid filename");
                    return
            else:
                fn = '_'.join([
                    socket.gethostname(),
                    datetime.datetime.now().strftime('%y%m%d_%H%M%S')])
            base_fn = os.path.join(video_directory, fn)
            full_fn = base_fn + '.h264'
            i = 0
            # if already exists, don't overwrite
            while os.path.exists(full_fn):
                full_fn = "%s_%i.h264" % (base_fn, i)
                i += 1
                if i > 100:
                    self.set_status(500)
                    self.write("Server Error: could not make unique filename")
                    return
            # get duration from kwargs
            if 'duration' not in kwargs or len(kwargs['duration']) == 0:
                self.set_status(400)
                self.write("Bad Request: missing duration")
                return
            if not kwargs['duration'].isdigit():
                d = kwargs['duration']
                if d[0] == '-' or d.lower() == 'inf':
                    v = 0  # continuous
                    m = 0
                elif d[-1] == 's':  # seconds
                    v = kwargs['duration'][:-1]
                    m = 1000
                elif d[-1] == 'm':  # minutes
                    v = kwargs['duration'][:-1]
                    m = 1000 * 60
                elif d[-1] == 'h':  # hours
                    v = kwargs['duration'][:-1]
                    m = 1000 * 60 * 60
                else:
                    self.set_status(400)
                    self.write("Bad Request: invalid duration[%s]" % d)
                try:
                    kwargs['duration'] = str(int(v) * m)
                except ValueError as e:
                    self.set_status(400)
                    self.write(
                        "Bad Request: invalid duration[%s:%s]" % (d, e))
            # start recording
            cmd = " ".join([
                "raspivid -t %s -n -o %s" % (kwargs['duration'], full_fn),
                self.application.grab_args])
            print("Starting recording: %s" % (cmd, ))
            self.application.record_process = subprocess.Popen(cmd.split())
            # return filename, status (recording or not)
            s = self.is_recording()
            r = {
                'fn': fn,
                'status': s,
            }
            if not s:
                r['error'] = self.application.error
            self.write(json.dumps(r))
        elif op == 'stop':
            if self.application.record_process is None:
                # TODO set status? self.set_status(200)
                # self.write("not recording, ignoring")
                return
            print("killing record process")
            # send kill to record_process
            self.application.record_process.kill()
            # join
            # TODO timeout
            print("waiting for record process to terminate")
            self.application.record_process.wait()
            print("setting record process to None")
            self.application.record_process = None
        elif op == 'shutdown':
            cmd = "sudo shutdown -h now"
            print("calling: %s" % (cmd, ))
            try:
                r = subprocess.check_output(cmd.split())
            except subprocess.CalledProcessError as e:
                self.set_status(500)
                self.write("shutdown failed: %s" % (e, ))
                return
        elif op == 'status':
            # get status
            status = {
                'recording': self.is_recording(),
                'space': self.get_disk_space(),
                'videos': sorted(self.get_video_filenames()),
                'grab_args': self.application.grab_args,
            }
            if self.application.error is not None:
                status['error'] = self.application.error
                self.application.error = None
            # json encode
            self.write(json.dumps(status))
        elif op == 'remove':
            # remove video filename
            if 'fn' not in kwargs:
                self.set_status(400)
                self.write("Bad Request: missing filename[fn]")
                return
            # sanitize input
            if self.check_filename(kwargs['fn']):
                self.set_status(400)
                self.write("Bad Request: invalid filename");
                return
            # remove video_directory + fn
            fn = kwargs['fn'] + '.h264'
            full_fn = os.path.join(video_directory, fn)
            if not os.path.exists(full_fn):
                self.set_status(400)
                self.write("Bad Request: filename does not exist[%s]" % (fn, ))
                return
            try:
                print("removing: %s" % (full_fn, ))
                os.remove(full_fn)
            except Exception as e:
                self.set_status(500)
                self.write("Failed to remove file[%s]: %s" % (fn, e))
                return
        elif op == 'config':
            # configure video/grab settings
            if 'args' not in kwargs:  # return config instead
                self.write(json.dumps(self.application.grab_args))
                #self.set_status(400)
                #self.write("Bad Request: missing arguments[args]")
                return
            s = urllib.parse.unquote(kwargs['args'])
            print("setting grab_args: %s" % (s, ))
            self.application.grab_args = s
            # save grab args
            print("saving grab_args to %s" % grab_args_fn)
            with open(grab_args_fn, 'w') as f:
                f.write(self.application.grab_args)
        else:  # invalid op
            self.set_status(400)
            self.write("Bad Request: unkonwn operation[op:%s]" % (op, ))
            return


class CamApplication(tornado.web.Application):
    def __init__(self, **kwargs):
        self.record_process = None
        self.error = None
        # load defaults
        if os.path.exists(grab_args_fn):
            with open(grab_args_fn, 'r') as f:
                self.grab_args = f.readline().strip()
        else:
            self.grab_args = "-w 100 -h 100"
        handlers = [
            (r"/", CamSite),
            (r"/camera", CamQuery),
            (
                r"/videos/(.*)",
                tornado.web.StaticFileHandler,
                {"path": video_directory}),
            (
                r"/static/(.*)",
                tornado.web.StaticFileHandler,
                {"path": static_directory}),
        ]
        super().__init__(handlers, **kwargs)


if __name__ == "__main__":
    for d in (static_directory, video_directory):
        if not os.path.exists(d):
            os.makedirs(d)
    server = tornado.httpserver.HTTPServer(CamApplication())
    server.listen(8888)
    tornado.ioloop.IOLoop.current().start()
