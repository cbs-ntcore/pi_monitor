#!/bin/bash

# TODO read worker from command line arguments
WORKER="worker1.local"

# exit on errors
set -e

# check that controller ssh keys exist
if [ ! -f ~/.ssh/id_rsa.pub ]; then
  echo "SSH keys don't yet exist, generating [accept all defaults]..."
  ssh-keygen
fi

# copy over ssh keys
rsync -tu --rsync-path="mkdir -p /home/pi/.ssh/ && rsync" ~/.ssh/id_rsa.pub $WORKER:~/.ssh/authorized_keys2

# TODO set hostname?

# set timezone on worker
TZ=`cat /etc/timezone`
ssh $WORKER sudo timedatectl set-timezone $TZ

# TODO setup systemd service

# set date on worker
DS=`date -I"seconds"`
ssh $WORKER sudo date --set=$DS
