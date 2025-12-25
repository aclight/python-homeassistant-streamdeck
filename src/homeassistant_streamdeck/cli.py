#!/usr/bin/env python3
"""Thin CLI wrapper that delegates to the top-level `HassClient` module.

This keeps the original `HassClient.py` as the canonical implementation
while exposing an installed console script entry point.
"""

import argparse
import asyncio
import logging
import os
import sys

# Import the Config class and main coroutine from the original script so we
# avoid duplicating logic here. This expects `HassClient.py` to be importable
# on `sys.path` (works for editable installs and running from the repo root).
from .HassClient import Config, main as hass_main


def _find_config_path(explicit_path=None):
    """Find and validate config file path.
    
    Search order:
    1. Explicit path via --config argument
    2. config.yaml in current working directory
    
    Raises:
        FileNotFoundError: If config file cannot be found
    """
    if explicit_path:
        if os.path.exists(explicit_path):
            return explicit_path
        else:
            raise FileNotFoundError(f"Config file not found: {explicit_path}")

    cwd_path = os.path.join(os.getcwd(), 'config.yaml')
    if os.path.exists(cwd_path):
        return cwd_path

    # No config found
    raise FileNotFoundError(
        "No config.yaml found.\n\n"
        "Please create a config.yaml file in your current directory, or provide\n"
        "the path using: hass-streamdeck --config /path/to/config.yaml\n\n"
        "See config.example.yaml for a complete example configuration."
    )


def run():
    parser = argparse.ArgumentParser(prog='hass-streamdeck')
    parser.add_argument('--config', '-c', help='Path to config.yaml (optional)')
    args = parser.parse_args()

    try:
        config_path = _find_config_path(args.config)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)

    config = Config(config_path)
    
    # Set logging level based on config debug flag
    log_level = logging.DEBUG if config.get('debug') else logging.INFO
    logging.basicConfig(level=log_level)
    
    try:
        asyncio.run(hass_main(config))
    except Exception:
        logging.exception("Fatal error in hass-streamdeck")
        sys.exit(1)


if __name__ == '__main__':
    run()
