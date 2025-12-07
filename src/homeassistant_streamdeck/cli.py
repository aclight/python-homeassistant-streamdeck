#!/usr/bin/env python3
"""CLI wrapper for running the Home Assistant StreamDeck client as an installed script.

This is adapted from the top-level `HassClient.py` so the project can be
installed and invoked as `hass-streamdeck`.
"""

from HomeAssistantWS.RemoteWS import HomeAssistantWS
from Tile.TileManager import TileManager

import StreamDeck.DeviceManager as StreamDeck
import logging
import asyncio
import yaml
import signal
import argparse
import importlib.resources as pkg_resources
import tempfile
import os

logging.basicConfig(level=logging.DEBUG)


class Config(object):
    def __init__(self, filename):
        try:
            logging.info('Reading config file "{}"...'.format(filename))

            with open(filename, 'r', encoding='utf-8') as config_file:
                self.config = yaml.safe_load(config_file)
        except IOError:
            logging.error('Failed to read config file "{}"!'.format(filename))

            self.config = {}

    def get(self, path, default=None):
        value = default

        location = self.config
        for fragment in path.split('/'):
            location = location.get(fragment, None)
            if location is None:
                return default

            value = location or default

        return value


class ScreenSaver:
    def __init__(self, deck):
        self.deck = deck

        deck.set_key_callback_async(self._handle_button_press)

    async def start(self, brightness, callback, timeout=0):
        self.brightness = brightness
        self.callback = callback
        self.timeout = timeout

        # schedule the screensaver loop on the currently running event loop
        asyncio.create_task(self._loop())

    async def _loop(self):
        await self._set_on()

        if self.timeout == 0:
            return

        while True:
            await asyncio.sleep(1)

            if self.on:
                self.steps -= 1
                if self.steps < 0:
                    await self._set_off()

    async def _set_on(self):
        self.deck.set_brightness(self.brightness)
        self.steps = self.timeout
        self.on = True

    async def _set_off(self):
        self.deck.set_brightness(0)
        self.steps = 0
        self.on = False

    async def _handle_button_press(self, deck, key, state):
        if self.on:
            self.steps = self.timeout
            await self.callback(deck, key, state)
        else:
            if not state:
                await self._set_on()


async def main(config):
    conf_deck_brightness = config.get('streamdeck/brightness', 20)
    conf_deck_screensaver = config.get('streamdeck/screensaver', 0)
    conf_hass_host = config.get('home_assistant/host', 'localhost')
    conf_hass_ssl = config.get('home_assistant/ssl', False)
    conf_hass_port = config.get('home_assistant/port', 8123)
    conf_hass_pw = config.get('home_assistant/api_password')
    conf_hass_token = config.get('home_assistant/api_token')

    decks = StreamDeck.DeviceManager().enumerate()
    if not decks:
        logging.error("No StreamDeck found.")
        return False

    deck = decks[0]
    hass = HomeAssistantWS(ssl=conf_hass_ssl, host=conf_hass_host, port=conf_hass_port)

    tiles = dict()
    pages = dict()

    tile_classes = getattr(__import__("Tile"), "Tile")

    # Build dictionary for the tile class templates given in the config file
    conf_tiles = config.get('tiles', [])
    for conf_tile in conf_tiles:
        conf_tile_type = conf_tile.get('type')
        conf_tile_class = conf_tile.get('class')
        conf_tile_action = conf_tile.get('action')
        conf_tile_states = conf_tile.get('states')

        tile_states = dict()
        for conf_tile_state in conf_tile_states:
            state = conf_tile_state.get('state')
            tile_states[state] = conf_tile_state

        tiles[conf_tile_type] = {
            'class': getattr(tile_classes, conf_tile_class),
            'states': tile_states,
            'action': conf_tile_action,
        }

    # Build dictionary of tile pages
    conf_screens = config.get('screens', [])
    for conf_screen in conf_screens:
        conf_screen_name = conf_screen.get('name')
        conf_screen_tiles = conf_screen.get('tiles')

        page_tiles = dict()
        for conf_screen_tile in conf_screen_tiles:
            conf_screen_tile_pos = conf_screen_tile.get('position')
            conf_screen_tile_type = conf_screen_tile.get('type')

            conf_tile_class_info = tiles.get(conf_screen_tile_type)

            page_tiles[tuple(conf_screen_tile_pos)] = conf_tile_class_info['class'](deck=deck, hass=hass, tile_class=conf_tile_class_info, tile_info=conf_screen_tile)

        pages[conf_screen_name] = page_tiles

    tile_manager = TileManager(deck, pages)

    async def hass_state_changed(data):
        await tile_manager.update_page(force_redraw=False)

    async def steamdeck_key_state_changed(deck, key, state):
        await tile_manager.button_state_changed(key, state)

    # enable loop-level debug settings if requested in config
    if config.get('debug'):
        logging.info('Debug enabled')
        loop = asyncio.get_running_loop()
        loop.set_debug(True)
        loop.slow_callback_duration = 0.15

    logging.info("Connecting to %s:%s...", conf_hass_host, conf_hass_port)
    try:
        await hass.connect(api_password=conf_hass_pw, api_token=conf_hass_token)
    except Exception:
        logging.exception("Failed to connect to Home Assistant")
        return

    deck.open()
    logging.info("Opening StreamDeck device and resetting device")
    try:
        deck.reset()
    except Exception:
        logging.exception("Failed to reset StreamDeck")

    try:
        # Ensure the device is awake and at a visible brightness (do this after reset)
        deck.set_brightness(conf_deck_brightness)
    except Exception:
        logging.exception("Failed to set initial StreamDeck brightness")

    screensaver = ScreenSaver(deck=deck)
    await screensaver.start(brightness=conf_deck_brightness, callback=steamdeck_key_state_changed, timeout=conf_deck_screensaver)

    await tile_manager.set_deck_page(None)
    await hass.subscribe_to_event('state_changed', hass_state_changed)

    # keep running until a termination signal; background tasks (receiver, callbacks) run on the event loop
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(s, stop_event.set)
        except NotImplementedError:
            # add_signal_handler may not be implemented on some platforms
            pass

    try:
        await stop_event.wait()
    finally:
        logging.info("Shutting down...")
        try:
            await hass.close()
        except Exception:
            logging.exception("Error closing Home Assistant connection")

        try:
            # Close the StreamDeck device cleanly if possible
            deck.close()
        except Exception:
            logging.exception("Error closing StreamDeck")


def _find_config_path(explicit_path=None):
    """Return a path to a config file to use.

    Priority:
    1. explicit_path if provided and exists
    2. `./config.yaml` in current working dir
    3. packaged `config.yaml` inside this package
    """
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
        asyncio.run(main(config))
    finally:
        # If we created a temp file, try to remove it
        if args.config is None and config_path and config_path.startswith(tempfile.gettempdir()):
            try:
                os.unlink(config_path)
            except Exception:
                pass


if __name__ == '__main__':
    run()
