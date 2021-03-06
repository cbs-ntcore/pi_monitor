Assumes you're running a raspberry pi with user pi

- clone repository to /home/pi/Repositories/cbs-ntcore/pi_monitor
- install requirements: "sudo apt install python3-tornado ntfs-3g"
- enable picamera (and usually ssh) using raspi-config
- run python code: "python3 /home/pi/Repositories/cbs-ntcore/pi_monitor/camserver.py"

to enable automount of usb drives to the videos directory

```
sudo ln -s /home/pi/Repositories/cbs-ntcore/pi_monitor/setup/rules/99-automount_storage.rules /etc/udev/rules.d/
```

add the following to the crontab to automatically start the server on reboot

```
@reboot sleep 10 && python3 /home/pi/Repositories/cbs-ntcore/pi_monitor/camserver.py
```

to use the pi as an access point run the following scripts:
```
cd /home/pi/Repositories/cbs-ntcore/pi_monitor/scripts
bash setup_ap.sh NEWSSID NEWPASSWORD
bash enable_ap.sh  # note this will take down any wifi connection
# run disable_ap.sh to disable the ap mode
```

For accurate LED control, add the following to /boot/config.txt then reboot
```
disable_camera_led=1
```

If when cloning a SD image you want to rename the pi, change the name in the following:

- /etc/hostapd/hostapd.conf
- /etc/hostname
- /etc/hosts
