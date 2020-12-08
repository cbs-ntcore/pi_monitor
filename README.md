Python software for network/web based configuration and control of camera recording
that turns a Pi into an extensible IP camera with intended uses for 
laboratory/scientific applications.


# Use cases

## Isolated system video monitoring

You want to record some videos of your subject but don't have a (reliable) network 
to attach your video monitor. You also might not have a keyboard, mouse and display
to attach to your monitor to configure the recording.

Instead, you want your monitor to broadcast it's own wifi network so that you 
can attach a phone (or tablet or computer) to the monitor's network to configure 
the camera and record some videos.

## Networked video monitoring

You want to record some videos of your subject and have a (reliable) network 
to which you'll connect your monitor. You'll use this network connection (and
the monitors IP address) to configure the camera and start/stop the recording.

For a small number of monitors, you can add multiple monitors to the same network 
and give them each different hostnames (e.g. monitor1, monitor2). This 
will allow you to connect to each monitor either using link-local zeroconf 
addressing (e.g. monitor1.local, monitor2.local) or by IP address (assigned 
statically or using DHCP).

## Cluster of video monitors

You want to record videos from a large number of subjects where you don't 
want to connec to each monitor directly to configure and enable recording.
Instead, you will setup a network to connect multiple monitors to one controller 
that will manage the monitors.


# Installation

For all use cases, you will need to setup a pi (or several) with the latest 
[Raspberry Pi OS with recommended software](https://www.raspberrypi.org/software/operating-systems/) 
(Aug 20, 2020 at time of writing but newer should work).

If you're setting up many pis you may want to consider setting up 1 (or 1 of each type) 
of pi then clone the uSD card image and write it to the remaining cards you need 
to setup. You will need to do some final configuration of the system 
on first boot (including changing the hostname and possibly the ip address).

## General Pi setup

Write the OS image to the SD card and setup for the first boot. If you are running 
a headless setup follow 
[these instructions](https://www.raspberrypi.org/documentation/configuration/wireless/headless.md) 
to setup wifi and SSH before booting. Otherwise, you will need to connect a keyboard 
mouse and monitor and setup a network connection to allow downloading this repository.

Boot the pi and run ```sudo raspi_config``` to setup the following:
- change hostname. This should be unique and might be the type of pi (e.g. monitor1, monitor2, controller1)
- change password. Don't use raspberry.
- change locale. If you're in the US then en_US UTF-8 works.
- change timezone. Note: there is no plan to support networked monitors in multiple timezones

Reboot the pi and check that the above settings are correct.

As you've installed the Raspberry Pi OS with recommended software you should have a 
system with git, ffmpeg, python3 and other dependencies.

Clone this repository onto the Pi

```bash
mkdir -p ~/r/cbs-ntcore
cd ~/r/cbs-ntcore
git clone https://github.com/cbs-ntcore/pi_monitor.git
```

## Networking

Depending on your use case you may have one of the following network structures.

### Isolated monitor

If you're running an isolated monitor and want it to broadcast it's own network you
will have to first setup the Pi with an outbound connection (one that can see 
the internet) so that you can download some dependencies (dnsmasq and hostapd).

See the scripts for some examples for setting up the Pi as an access point.
setup_ap.sh will install dependencies and setup configuration files for a wifi network 
with name NEWSSID and password NEWPASSWORD (or whatever you provide as arguments 
to the script.

```bash
cd ~/r/cbs-ntcore/pi_monitor/scripts
bash setup_ap.sh NEWSSID NEWPASSWORD
bash enable_ap.sh  # note this will take down any wifi connection
# run disable_ap.sh to disable the ap mode
```

### Networked monitor(s)

The precise setup for this use case will depend on the network you're using to 
connect the monitors. In the end you will need to know the ip addresses of each 
monitor and have access to each ip at port 8000 (as default, this can be changed).

If you've connected each monitor to a dhcp-enabled network you might have luck using 
zeroconf to find monitors based on hostname by attempting to connect to hostname.local
(for a monitor with hostname monitor1 this would be monitor1.local) either using ssh
or in the web browser. Note that using dhcp assigned ip addresses will mean that 
your monitors might change their ip address on lease renewal and/or reboot. To 
overcome this issue it may be possible to reserve an ip for a particular monitor.
This might require getting the mac address of the monitor/Pi which can be seen by 
running ```ifconfig``` and examining the ether value for the appropriate network 
interface (eth0 for wired, wlan0 for wireless).

You may want to follow the description below for setting up SSH keys to make
accessing monitors easier (by not requiring a password on SSH connection).

### Clustered monitor(s)

For this use case you will likely be setting up a separate network that contains 
the monitors and a controller Pi connected using wired connections. If you're 
using a network switch (instead of a router) you will likely not have a dhcp 
server on the network and have to manually assign ip addresses for each Pi
(it's possible to rely on link-local addresses assigned via zeroconf however 
this is not recommended as duplicate hostnames can cause renaming and access 
issues).

One example static ip assignment strategy is to give monitors ip addresses starting
at 192.168.2.1 (for monitor1) and assign the controller to 192.168.2.100 
(assuming you don't have >99 monitors). This can be done several ways including:

- through the network gui
- by modifying /etc/dhcpcd.conf
- adding the ip to the end of the first line in /boot/cmdline.txt in the form ```ip=192.168.2.1```

When you have a system with valid ip addresses you will next want to setup ssh keys:

1) on the controller Pi, generate ssh keys using ```ssh-keygen``` accepting all 
defaults. This will generate some files in ~/.ssh/ containing your new secret key
2) on the controller Pi, copy your id_rsa.pub file to a new file named authorized_keys2
```cp ~/.ssh/id_rsa.pub ~/.ssh/authorized_keys2```. This step makes the controller Pi
accessable (without a password) from a computer that has the secret key.
3) copy the keys (and the new authorized_keys2) to each monitor. For example to copy files 
over the network to monitor1 (assuming it's at 192.168.2.1) use the following: 
```cd ~/.ssh/ && rsync id_rsa id_rsa.pub authorized_keys2 192.168.2.1:~/.ssh/```
4) verify that you can connect to a worker using ssh ```ssh 192.168.2.1``` without 
being asked for a password (the terminal prompt will display the current hostname 
which should help you know what system you're logged in to).
5) after sshing into the monitor, ssh back into the controller ```ssh 192.168.2.100```
to make sure key based ssh connections are setup both ways (monitor to controller and 
controller to monitor)
6) to exit out of an ssh connection type ```exit```


# How to use

For testing it can be helpful to call the monitor software directly from the command line using:

```bash
cd ~/r/cbs-ntcore/pi_monitor
python3 -m pi_monitor
```

By default, this will start a web server hosting on all interfaces on port 8000. To 
view the website visit http://127.0.0.1:8000/monitor.html (on the same computer as 
monitor code).

Configure camera by adjusting settings in gear at top right of page
Start/stop streaming by clicking button at top left (streaming during recording might cause video errors)
See current files near bottom of page. Files can be downloaded, converted (to mp4) and removed (after checking 'Allow Removal' [this removal is **PERMANENT**])
See current errors at bottom of page (refreshing the page clears these)

If you'd like the code to start automatically on reboot you have two options.

First, you can add the following to your crontab on the monitor Pi
(run ```crontab -e``` to edit your crontab):
```@reboot sleep 10 && cd /home/pi/r/cbs-ntcore/pi_monitor && python3 -m pi_monitor```
This code will wait 10 seconds on startup (to allow the network to come up) and then 
start the code.

The second option is the enable the systemd service services/monitor.service by
running:
```bash
# change to the pi_monitor/services directory
cd ~/r/cbs-ntcore/pi_monitor/services
# link service to systemd system services directory
sudo ln -s monitor.service /etc/systemd/system/monitor.service
# enable the service to automatically start on boot
sudo systemctl enable monitor.service
# start the service for this session
sudo systemctl start monitor.service
```
Using this option allows you to see log output and system status using the following:
```bash
# to see the current status of the service
sudo systemctl status monitor.service
# to see the log output of the current or last run of the service
sudo journalctl -u monitor.service
```
