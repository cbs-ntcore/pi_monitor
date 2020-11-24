import re
import subprocess


date_string_re = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+[0-9]{2}:[0-9]{2}")


class SystemControl:
    def shutdown(self):
        return subprocess.check_output("sudo shutdown -h now".split())

    def reboot(self):
        return subprocess.check_output("sudo reboot".split())
    
    def set_date(self, datetime):
        """Use format from date -I"seconds" (example: 2020-08-25T16:32:15+01:00)"""
        if not date_string_re.match(datetime):
            raise Exception("set_date: Invalid format see output of date -I'seconds'")
        return subprocess.check_output(f"sudo date --set='{datetime}'".split())
