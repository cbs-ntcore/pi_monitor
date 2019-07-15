#!/usr/bin/env python3
"""
Control N camera servers

show of single image: /camera/grab
show list of videos, status, space on disk: /camera/status
configure recording: /camera/config
control recording: /camera/record

need way to 'add' camservers (by hostname) (and remove)

urls:
    /: show site
    /control:
        camera=hostname,op=etc...: relay camera query
        remove=hostname: remove camera from list
        *: get list of cameras
"""

import datetime
import json
import os
import socket
import sys
import time
import urllib.parse
import urllib.request

import tornado
import tornado.httpserver
import tornado.ioloop
import tornado.web


this_directory = os.path.dirname(os.path.realpath(__file__))
static_directory = os.path.join(this_directory, 'static')


class ControlSite(tornado.web.RequestHandler):
    def get(self):
        template = os.path.join(this_directory, 'templates', 'control.html')
        self.render(template)


class ControlQuery(tornado.web.RequestHandler):
    def get(self):
        pass

    def add_camera(self, camera):
        print("adding new camera: %s" % (camera, ))
        # lookup ip
        self.application.cameras[camera] = socket.gethostbyname(camera)

    def remove_camera(self, camera):
        if camera in self.application.cameras:
            del self.application.cameras[camera]

    def camera_query(self, camera, query):
        url = "http://%s:8888/camera" % camera
        data = urllib.parse.urlencode(query).encode('latin')
        print("Request: %s, [%s]=%s" % (url, query, data))
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(query).encode('latin'))
        try:
            res = urllib.request.urlopen(req)
        except urllib.request.HTTPError as e:
            print("Error: %s" % (e, ))
            res = e
        # relay headers, status code, data
        if hasattr(res, 'read'):
            print("Relaying data")
            #data = res.read()
            #self.write(data)
            self.write(res.read())
        # do this after writing to overwrite headers
        for h in res.headers.items():
            print("set_header: %s" % (h, ))
            self.set_header(*h)
        print("set_header: %s" % (h, ))
        self.set_status(res.status)

    def post(self):
        args = list(self.request.arguments.keys())
        kwargs = {k: self.get_argument(k) for k in args}
        print("POST: %s" % (kwargs, ))
        if 'camera' not in kwargs:
            if 'remove' in kwargs:
                # remove camera from list
                self.remove_camera(kwargs['remove'])
            else:
                # return list of cameras
                self.write(json.dumps(sorted(list(self.application.cameras.keys()))))
            return
        camera = kwargs['camera']
        if camera not in self.application.cameras:
            self.add_camera(camera)
        del kwargs['camera']
        # pass on camera query
        self.camera_query(camera, kwargs)


class ControlApplication(tornado.web.Application):
    def __init__(self, **kwargs):
        # TODO allow init with default list
        self.cameras = {}
        handlers = [
            (r"/", ControlSite),
            (r"/control", ControlQuery),
            (
                r"/static/(.*)",
                tornado.web.StaticFileHandler,
                {"path": static_directory}),
        ]
        super().__init__(handlers, **kwargs)


if __name__ == "__main__":
    server = tornado.httpserver.HTTPServer(ControlApplication())
    server.listen(8080)
    tornado.ioloop.IOLoop.current().start()
