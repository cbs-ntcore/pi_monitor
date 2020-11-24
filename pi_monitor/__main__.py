"""
Usage:
    python3 -m pi_monitor camera  # start camera node, default
    python3 -m pi_monitor control  # start control node
"""

import sys

from . import camera

import logging
logging.basicConfig(level=logging.DEBUG)

if __name__ == '__main__':
    node = 'camera'
    if len(sys.argv) > 1:
        node = sys.argv[1]

    if node == 'camera':
        camera.run()
    elif node == 'control':
        raise NotImplementedError(f"Node {node} not implemented")
    else:
        raise Exception(f"Unknown node {node}")
