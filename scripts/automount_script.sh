#!/bin/bash

# stop on error
set -e

# check if user is root
if [[ $EUID -ne 0 ]]; then
    echo "Must be run as root"
    exit 1
fi

# look through all sd*
for DRIVE in `find /dev -name sd[a-z][0-9]`; do
    # check if already mounted
    if mount -l | grep $DRIVE; then
        continue
    fi

    # if not mounted, mount to /media using name
    LABEL=`blkid $DRIVE -o export | grep ^LABEL= | awk -F "=" '{print $2}'`
    if [ ! -d "/media/$LABEL" ]; then
        mkdir /media/$LABEL
    fi
    mount $DRIVE /media/$LABEL

    # change permissions
    chmod 777 /media/$LABEL
done
