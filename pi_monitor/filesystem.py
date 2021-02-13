"""
disk space
videos
- list
- convert
- remove
"""
import glob
import logging
import os
import subprocess
import threading
import time

import psutil


cmd_template = "ffmpeg -i {src} -vcodec copy {dst}"


def build_conversion_command(src, dst=None):
    if not os.path.exists(src):
        raise FileNotFoundError(f"{src} does not exist")
    if dst is None:
        dst = os.path.splitext(src)[0] + '.mp4'
    if dst == src:
        raise FileExistsError(f"{src} and {dst} cannot be equal")
    if not os.path.exists(os.path.dirname(dst)):
        os.makedirs(os.path.dirname(dst))
    if os.path.exists(dst):
        raise FileExistsError(f"{dst} exists, refusing to overwrite")
    return cmd_template.format(src=src, dst=dst)


def value_to_metric_prefix_string(value):
    for (p, v) in (('T', 1E12), ('G', 1E9), ('M', 1E6), ('K', 1E3)):
        if value >= v:
            return "{:0.2f}{}".format(value / v, p)
    return str(value)


class FileSystem:
    def __init__(self):
        self.conversion_process = None
        self._static_directory = None
        self.scan_for_drives()

    def static_directory(self, new_directory=None):
        if new_directory is not None:
            self._static_directory = new_directory
        return self._static_directory

    def get_disk_space(self, directory='/'):
        return psutil.disk_usage(directory).free

    def get_filenames(self, directory):
        return os.listdir(directory)

    def get_open_files(self):
        parent = psutil.Process()
        while 'python' in parent.parent().name():
            parent = parent.parent()
        procs = [parent, ] + parent.children(recursive=True)
        finfo = []
        for p in procs:
            for f in p.open_files():
                finfo.append([f.path, p.pid, f.fd])
        return finfo

    def get_file_info(self, directory, recursive=False):
        d = os.path.normpath(directory) + os.sep
        open_files = {
            os.path.relpath(fpath, d): fpid for (fpath, fpid, _)
            in self.get_open_files()
            if os.path.abspath(fpath).startswith(d)}
        if not recursive:
            return [{
                'name': fn,
                'size': os.stat(os.path.join(directory, fn)).st_size,
                'open': fn in open_files,
                } for fn in os.listdir(directory)]
        file_info = []
        for subdir, _, filenames in os.walk(directory):
            for fn in filenames:
                sfn = os.path.join(subdir, fn)
                rfn = os.path.relpath(sfn, directory)
                file_info.append({
                    'name': rfn,
                    'size': os.stat(sfn).st_size,
                    'open': rfn in open_files
                })
        return file_info

    def get_files_to_convert(self, directory):
        finfo = {i['name']: i for i in self.get_file_info(directory)}
        to_convert = []
        for fn in finfo:
            root, ext = os.path.splitext(fn)
            if ext == '.h264' and f'{root}.mp4' not in finfo:
                to_convert.append(os.path.join(directory, fn))
        return to_convert

    def convert_all_files(self, directory):
        if self.is_converting():
            # TODO setup conversion queue
            raise Exception("Only 1 conversion allowed at a time")

        # check if any files need conversion
        to_convert = self.get_files_to_convert(directory)
        print("to_convert {}".format(to_convert))
        if not len(to_convert):
            return

        # setup thread to start and monitor conversion
        def run_conversion(fns):
            for fn in fns:
                self.convert_video(fn)
                while self.is_converting():
                    time.sleep(0.1)

        thread = threading.Thread(target=run_conversion, args=(to_convert, ))
        thread.start()

    def is_converting(self):
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
        if self.is_converting():
            # TODO setup conversion queue
            raise Exception("Only 1 conversion allowed at a time")

        # start conversion
        cmd = build_conversion_command(filename)
        logging.debug(f"convert_video: {cmd}")
        self.conversion_process = subprocess.Popen(cmd.split())

        # check conversion is running
        return self.is_converting()

    def delete_file(self, filename):
        os.remove(filename)

    def scan_for_drives(self):
        drives = [p for p in glob.glob('/dev/sd*') if p[-1].isdigit()]
        if len(drives) == 0:
            return
        # check if all drives are mounted
        with open('/proc/mounts', 'r') as f:
            for l in f:
                l = l.strip()
                if len(l) == 0:
                    continue
                found = None
                for d in drives:
                    if d in l:
                        found = d
                        break
                if found is not None:
                    drives.remove(found)
                    continue
        if len(drives) == 0:
            return

        # get labels of drives
        labels = {}
        for label_symlink in glob.glob('/dev/disk/by-label/*'):
            dev_path = os.path.realpath(label_symlink)
            labels[dev_path] = os.path.basename(label_symlink)

        for drive in drives:
            if drive not in labels:
                logging.warning(f"Found drive {drive} with missing label")
                continue
            # check that mount point exists
            mount_path = "/media/" + labels[drive]
            if not os.path.exists(mount_path):
                subprocess.check_call(["sudo", "mkdir", mount_path])
                subprocess.check_call(["sudo", "chmod", "777", mount_path])

            # mount drive
            subprocess.check_call(["sudo", "mount", drive, mount_path])

