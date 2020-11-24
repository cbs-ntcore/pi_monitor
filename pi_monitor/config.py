"""
Configuration including:
- video directory
- temporary directory
- default settings (exposure, resolution, led, etc...)
- repeat recordings (cron like)
- filesystem limits before video deletion
- filename templating

Configuration set from:
- home directory file: ~/.pi_monitor/config [json?]
- reconfiguration from web requests [json]
"""

import json
import logging
import os


def load(fn, default=None):
    if default is None:
        default = {}
    if not os.path.exists(fn):
        logging.debug(f"No config found in {fn} returning default")
        return default
    logging.debug(f"Loading config from {fn}")
    with open(fn, 'r') as f:
        config = json.load(f)
    return config


def save(config, fn):
    logging.debug(f"Saving config to {fn}")
    d = os.path.dirname(os.path.abspath(fn))
    if not os.path.exists(d):
        os.makedirs(d)
    with open(fn, 'w') as f:
        json.dump(config, f)
