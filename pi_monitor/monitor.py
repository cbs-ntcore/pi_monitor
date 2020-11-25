"""
Web server running on a pi with a camera
"""

from . import backend
from . import camera
from . import filesystem
from . import sysctl


def run(*args, **kwargs):
    backend.register(
        camera.CameraThread, r'^/camera/.??',
        init=lambda o: o.start(), deinit=lambda o: o.stop())
    backend.register(
        sysctl.SystemControl, r'^/system/.??')
    backend.register(
        filesystem.FileSystem, r'^/filesystem/.??')
    backend.serve(*args, **kwargs)
