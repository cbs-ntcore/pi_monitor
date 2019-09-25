#!/bin/bash

# halt on error
set -e

# first argument should be ssid
if [ -z "$1" ]; then
  echo "No SSID provided"
  exit 1
fi

# second argument should be password
if [ -z "$2" ]; then
  echo "No password provided"
  exit 1
fi

# install requirements
sudo apt install dnsmasq hostapd

# stop services
sudo systemctl stop dnsmasq
sudo systemctl stop hostapd

if [ -e /etc/dhcpcd.conf ]; then
  sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.client
  sudo cp /etc/dhcpcd.conf /etc/dhcpcd.conf.ap
else
  sudo touch /etc/dhcpcd.conf.client
  sudo touch /etc/dhcpcd.conf.ap
fi

# configure dhcpcd.conf for ap mode
sudo tee -a /etc/dhcpcd.conf.ap > /dev/null << EOT
nohook wpa_supplicant
interface wlan0
static ip_address=10.0.0.1/24
static broadcast_address=10.0.0.255
EOT

# configure dns
sudo cp /etc/dnsmasq.conf /etc/dnsmasq.conf.orig
sudo tee -a /etc/dnsmasq.conf > /dev/null << EOT
interface=wlan0
dhcp-range=10.0.0.2,10.0.0.5,255.255.255.0,12h
EOT

# configure access point
if [ -e /etc/hostapd/hostapd.conf ]; then
    sudo cp /etc/hostapd/hostapd.conf /etc/hostapd/hostapd.conf.orig
fi

sudo tee -a /etc/hostapd/hostapd.conf > /dev/null << EOT
interface=wlan0
hw_mode=g
channel=10
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
wpa_passphrase=$2
ssid=$1
ieee80211n=1
wmm_enabled=0
ht_capab=[HT40][SHORT-GI-20][DSSS_CCK-40]
EOT

# enable access point
bash enable_ap.sh
