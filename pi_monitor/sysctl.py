import datetime
import re
import subprocess


local_timezone = datetime.datetime.now(datetime.timezone.utc).astimezone().tzinfo
date_string_re = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}[\+\-][0-9]{2}:[0-9]{2}")


def date_formatted_datetime():
    dt = datetime.datetime.now(datetime.timezone.utc).astimezone(local_timezone)
    s = dt.strftime('%Y-%m-%dT%H:%M:%S%z')
    # add colon to match output/input of date -I"seconds"
    return s[:-2] + ':' + s[-2:]


class SystemControl:
    def shutdown(self):
        return subprocess.check_output("sudo shutdown -h now".split())

    def reboot(self):
        return subprocess.check_output("sudo reboot".split())

    def restart_service(self):
        return subprocess.check_output("sudo systemctl restart monitor".split())
    
    def set_date(self, datetime):
        """Use format from date -I"seconds" (example: 2020-08-25T16:32:15+01:00)"""
        if not date_string_re.match(datetime):
            raise Exception("set_date: Invalid format see output of date -I'seconds'")
        return subprocess.check_output(
            f"sudo date --set={datetime}", shell=True).decode('ascii')
    
    def get_date(self):
        return date_formatted_datetime()
