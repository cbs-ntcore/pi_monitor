class SystemControl:
    def shutdown(self):
        return subprocess.check_output("sudo shutdown -h now".split())

    def reboot(self):
        return subprocess.check_output("sudo reboot".split())
