import time

import PIL.Image
import PIL.ImageDraw


def record_time(func):
    name = func.__name__
    def wrapped(self, *args, **kwargs):
        if name not in self.calls:
            self.calls[name] = []
        self.calls[name].append(time.time())
        return func(self, *args, **kwargs)
    return wrapped


class Frame:
    def __init__(self):
        self._index = -1
        self._t0 = time.monotonic()

    @property
    def index(self):
        self._index += 1
        return self._index

    @property
    def timestamp(self):
        return time.monotonic() - self._t0


class PiCamera:
    def __init__(self):
        self.__mock__ = True
        self.calls = {}
        self.frame = Frame()
        self.frame_count = 0

    @record_time
    def wait_recording(self, *args, **kwargs):
        pass

    @record_time
    def start_recording(self, *args, **kwargs):
        pass

    @record_time
    def split_recording(self, *args, **kwargs):
        pass

    @record_time
    def stop_recording(self, *args, **kwargs):
        pass

    @record_time
    def capture(self, f, *args, **kwargs):
        resize = kwargs.get('resize', (320, 240))

        # make jpeg of resize size
        frame = PIL.Image.new('RGB', resize)
        
        # draw something on the image
        draw = PIL.ImageDraw.Draw(frame)
        draw.text(
            (20, 20), "Test: {:04d}".format(self.frame_count),
            fill=(255, 255, 255))
        self.frame_count += 1

        # write to f
        frame.save(f, 'JPEG')
