#!/usr/bin/env python3
"""Thin CLI wrapper that delegates to the top-level `HassClient` module.

This keeps the original `HassClient.py` as the canonical implementation
while exposing an installed console script entry point.
"""

import argparse
import asyncio
import importlib.resources as pkg_resources
import tempfile
import os
import logging

# Import the Config class and main coroutine from the original script so we
# avoid duplicating logic here. This expects `HassClient.py` to be importable
# on `sys.path` (works for editable installs and running from the repo root).
from .HassClient import Config, main as hass_main


def _find_config_path(explicit_path=None):
    if explicit_path:
        if os.path.exists(explicit_path):
            return explicit_path
        else:
            raise FileNotFoundError(f"Config file not found: {explicit_path}")

    cwd_path = os.path.join(os.getcwd(), 'config.yaml')
    if os.path.exists(cwd_path):
        return cwd_path

    # Fallback to packaged config
    try:
        data = pkg_resources.files('homeassistant_streamdeck').joinpath('config.yaml').read_text(encoding='utf-8')
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.yaml')
        tmp.write(data.encode('utf-8'))
        tmp.close()
        return tmp.name
    except Exception:
        raise FileNotFoundError('No config.yaml found in CWD and packaged config is unavailable')


def run():
    parser = argparse.ArgumentParser(prog='hass-streamdeck')
    parser.add_argument('--config', '-c', help='Path to config.yaml (optional)')
    args = parser.parse_args()

    try:
        config_path = _find_config_path(args.config)
    except FileNotFoundError as exc:
        logging.error(str(exc))
        return 2

    config = Config(config_path)

    try:
        asyncio.run(hass_main(config))
    finally:
        # If we created a temp file, try to remove it
        if args.config is None and config_path and config_path.startswith(tempfile.gettempdir()):
            try:
                os.unlink(config_path)
            except Exception:
                pass


if __name__ == '__main__':
    run()
