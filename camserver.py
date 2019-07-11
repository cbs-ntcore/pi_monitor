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
    status: get recording status
    space: get space on disk (in video directory)
    remove: remove video file
    config: set grab/record settings
    videos: list available videos    
    op: (grab/record/status/space/remove/config)
"""

import datetime
import json
import os
import socket
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


class CamSite(tornado.web.RequestHandler):
    def get(self):
        template = os.path.join(this_directory, 'index.html')


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

    def get_n_videos(self):
        return len(os.listdir(video_directory))

    def get(self):
        self.return_image()

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
        elif op == 'record':
            # record video (if not recording)
            if self.is_recording():
                self.set_status(400)
                self.write("Bad Request: already recording")
                return
            # get filename from kwargs (or make a new one)
            if 'fn' in kwargs:
                fn = kwargs['fn']
                # TODO sanitize filename (no slashes, periods, spaces, etc)
            else:
                fn = '_'.join([
                    socket.gethostname(),
                    datetime.datetime.now().strftime('%y%m%d_%H%M%S')])
            fn += '.h264'
            full_fn = os.path.join(video_directory, fn)
            # TODO if already exists, don't overwrite
            # get duration from kwargs
            if 'duration' not in kwargs:
                self.set_status(400)
                self.write("Bad Request: missing duration")
                return
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
        elif op == 'status':
            # get status (recording?, space?, n_videos?)
            status = {
                'recording': self.is_recording(),
                'space': self.get_disk_space(),
                'n_videos': self.get_n_videos(),
            }
            if self.application.error is not None:
                status['error'] = self.application.error
                self.application.error = None
            # json encode
            self.write(json.dumps(status))
        elif op == 'videos':
            fns = os.listdir(video_directory)
            self.write(json.dumps(fns))
        elif op == 'remove':
            # remove video filename
            if 'fn' not in kwargs:
                self.set_status(400)
                self.write("Bad Request: missing filename[fn]")
                return
            # TODO sanitize input
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
            if 'args' not in kwargs:
                self.set_status(400)
                self.write("Bad Request: missing arguments[args]")
                return
            s = urllib.parse.unquote(kwargs['args'])
            print("setting grab_args: %s" % (s, ))
            self.application.grab_args = s
        else:  # invalid op
            self.set_status(400)
            self.write("Bad Request: unkonwn operation[op:%s]" % (op, ))
            return


class CamApplication(tornado.web.Application):
    def __init__(self, **kwargs):
        self.record_process = None
        self.error = None
        self.grab_args = ""
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
