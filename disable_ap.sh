#!/bin/bash

#sudo ln -sf /etc/network/interfaces.client /etc/network/interfaces
sudo ln -sf /etc/dhcpcd.conf.client /etc/dhcpcd.conf

sudo systemctl stop hostapd
sudo systemctl stop dnsmasq

sudo systemctl disable dnsmasq
sudo systemctl disable hostapd

sudo systemctl mask dnsmasq
sudo systemctl mask hostapd

sudo ip addr flush dev wlan0
sudo service dhcpcd restart

