import json
import http.server
import logging
import os
import re
import socketserver
import webbrowser


script_path = os.path.abspath(__file__)
static_directory = os.path.join(os.path.dirname(script_path), 'static')


def process_request(obj, request):
    method = request['method']
    args = request.get('args', ())
    kwargs = request.get('kwargs', {})
    logging.debug(f"process_request({obj}, {request})")
    return getattr(obj, method)(*args, **kwargs)


def process_json_request(obj, request_json):
    """
    Protocol:
        call = {
            method: 
            (optional) args:
            (optional) kwargs:
        }
        returns = {
            type: error/not-error,
            result: anything (json encodable)
        }
    """
    try:
        logging.debug(f"process_json_request({obj}, {request_json})")
        request = json.loads(request_json)
        result = process_request(obj, request)
        return json.dumps({
            'type': 'result',
            'result': result})
    except Exception as e:
        return json.dumps({'type': 'error', 'error': str(e)})


class ObjectHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):

    objects = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=static_directory, **kwargs)

    @classmethod
    def register(cls, obj, path_re):
        if not isinstance(path_re, re.Pattern):
            path_re = re.compile(path_re)
        logging.debug("Registering object[{}] at path {}".format(obj, path_re))
        cls.objects[path_re] = obj

    def do_POST(self):
        logging.debug("POST: {}".format(self.path))
        logging.debug("headers: {}".format(self.headers))
        logging.debug("Content-length: {}".format(self.headers['Content-length']))
        matched = False
        for obj_re in self.objects:
            if obj_re.match(self.path):
                logging.debug("Running request on {}".format(self.objects[obj_re]))
                s = process_json_request(
                    self.objects[obj_re],
                    self.rfile.read(int(self.headers['Content-length'])))
                logging.debug("Request result".format(s))
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Content-length', len(s))
                self.end_headers()
                self.wfile.write(str.encode(s))
                matched = True
        #if not matched:
        #    super().do_POST()


def register(*args, **kwargs):
    ObjectHTTPRequestHandler.register(*args, **kwargs)


def run_forever(open_browser=True, host=None, port=8000):
    # expects that some object has already been registered
    if len(ObjectHTTPRequestHandler.objects) == 0:
        logging.warning("No objects registered prior to serving")
    if host is None:
        host = ""
    # setup server
    socketserver.TCPServer.allow_reuse_address = True
    if open_browser:
        if host == "":
            url = "http://127.0.0.1:%s" % port
        else:
            url = "http://%s:%s" % (host, port)
        webbrowser.open(url)
    with socketserver.TCPServer((host, port), ObjectHTTPRequestHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass
