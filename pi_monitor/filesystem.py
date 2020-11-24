"""
disk space
videos
- list
- convert
- remove
"""

import os
import subprocess


cmd_template = "ffmpeg -i {src} -vcodec copy {dst}"


def build_conversion_command(src, dst=None):
    if not os.path.exists(src):
        raise FileNotFoundError(f"{src} does not exist")
    if dst is None:
        dst = os.path.basename(src) + '.mp4'
    if dst == src:
        raise FileExistsError(f"{src} and {dst} cannot be equal")
    if not os.path.dirname(dst):
        os.makedirs(os.path.dirname(dst))
    return cmd_template.format(src=src, dst=dst)


class FileSystem:
    def __init__(self):
        self.conversion_process = None

    def get_disk_space(self, directory='/'):
        cmd = "df -h %s" % directory
        output = subprocess.check_output(cmd, shell=True).decode('latin8')
        lines = output.strip().split(os.linesep)
        l = lines[-1]
        ts = l.split()
        space, used, avail, perc = ts[1], ts[2], ts[3], ts[4]
        return avail

    def get_filenames(self, directory):
        fns = [os.path.splitext(fn) for fn in os.listdir(directory)]
        return fns

    def is_conversion_running(self):
        if self.conversion_process is None:
            return False
        # check if process is done
        r = self.conversion_process.poll()
        if r is None:
            return True
        self.conversion_process = None
        if r == 0:  # all ok
            return False
        raise Exception(f"Conversion failed with return code {r}")

    def convert_video(self, filename):
        # check existing conversion is done
        if self.is_conversion_running():
            raise Exception("Only 1 conversion allowed at a time")

        # start conversion
        self.conversion_process = subprocess.Popen(
            build_conversion_command(filename))

        # check conversion is running
        return self.is_conversion_running()

    def get_file(self, filename):
        pass

    def delete_file(self, filename):
        pass
