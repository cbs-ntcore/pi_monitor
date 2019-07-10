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
    
    op: (grab/record/status/space/remove/config)
"""

import datetime
import json
import os
import sys
import time

import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web


this_directory = os.path.dirname(os.path.realpath(__file__))
static_directory = os.path.join(this_directory, 'static')
video_directory = os.path.join(this_directory, 'videos')

raspivid_process = None


class CamSite(tornado.web.RequestHandler):
    def get(self):
        template = os.path.join(this_directory, 'index.html')


class CamQuery(tornado.web.RequestHandler):
    def post(self):
        args = list(self.request.arguments.keys())
        kwargs = {k: self.get_argument(k) for k in args}
        if 'op' not in kwargs:
            self.set_status(400)  # bad request
            self.write("Bad Request: missing operation[op]")
        op = kwargs['op']
        if op == 'grab':
            # grab camera frame
            # return as jpeg
            pass
        elif op == 'record':
            # record video (if not recording)
            pass
        elif op == 'status':
            # get status (recording?, space?, n_videos?)
            pass
        elif op == 'space':
            # get space on disk
            pass
        elif op == 'remove':
            # remove video filename
            pass
        elif op == 'config':
            # configure video/grab settings
            pass
        else:  # invalid op
            pass
        pass


class CamApplication(tornado.web.Application):
    def __init__(self, **kwargs):
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
