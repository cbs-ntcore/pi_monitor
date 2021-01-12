"""
Usage:
    python3 -m pi_monitor camera  # start camera node, default
    python3 -m pi_monitor control  # start control node
"""

import logging
import os
import sys

if os.environ.get('PM_DEBUG', 0):
    logging.basicConfig(level=logging.DEBUG)

try:
    from . import avmonitor
except ImportError as e:
    logging.error(f"Failed to import avmonitor, likely missing pyaudio: {e}")
from . import camera
from . import controller
from . import monitor


if __name__ == '__main__':
    node = 'monitor'
    if len(sys.argv) > 1:
        node = sys.argv[1]

    if node == 'camera':
        camera.run()
    elif node == 'test':
        camera.test()
    elif node == 'monitor':
        monitor.run()
    elif node == 'avmonitor':
        avmonitor.run()
    elif node == 'controller':
        controller.run()
    else:
        raise Exception(f"Unknown node {node}")
