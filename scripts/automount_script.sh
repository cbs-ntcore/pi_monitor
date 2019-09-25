#!/bin/bash

VIDDIR="/home/pi/Repositories/cbs-ntcore/pi_monitor/videos"

# if videos symlink is good, ignore
if [ -e "$VIDDIR" ]; then
    echo "video symlink already valid"
    exit 0
fi

# find newly attached drive
if [ -z "$DEVNAME" ]; then
   echo "no devname found"
   exit 0
fi

# get uuid for first partition of drive
DRIVE=`blkid ${DEVNAME}1 -o value | head -n 1`

# if no drive, skip
if [ -z "$DRIVE" ]; then
    echo "no drive found"
    exit 0
fi

# link drive to videos directory
ln -sf /media/pi/$DRIVE $VIDDIR
