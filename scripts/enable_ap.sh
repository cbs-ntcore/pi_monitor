#!/bin/bash

#sudo ln -sf /etc/network/interfaces.ap /etc/network/interfaces
sudo ln -sf /etc/dhcpcd.conf.ap /etc/dhcpcd.conf

sudo systemctl unmask dnsmasq
sudo systemctl unmask hostapd

sudo systemctl enable dnsmasq
sudo systemctl enable hostapd

sudo ip addr flush dev wlan0
sudo service dhcpcd restart

sudo systemctl restart hostapd
sudo systemctl restart dnsmasq
