"""
disk space
videos
- list
- convert
- remove
"""

import os
import subprocess


class FileSystem:
    def __init__(self):
        pass

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

    def convert_video(self, filename):
        # TODO queue up thread to convert video
        pass

    def get_file(self, filename):
        pass

    def delete_file(self, filename):
        pass
