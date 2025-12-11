#!/usr/bin/env python3

#   Python StreamDeck HomeAssistant Client
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

from HomeAssistantWS.RemoteWS import HomeAssistantWS
from Tile.TileManager import TileManager

import StreamDeck.DeviceManager as StreamDeck
import logging
import asyncio
import yaml
import signal
import os
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

class Config(object):
    # Sensitive keys that can be overridden by environment variables
    SENSITIVE_KEYS = {
        'home_assistant/api_password': 'HASS_API_PASSWORD',
        'home_assistant/api_token': 'HASS_API_TOKEN',
    }

    def __init__(self, filename):
        # Try to load .env file for environment variables (optional dependency)
        self._load_dotenv()

        self.filename = filename
        self.config_dir = os.path.dirname(os.path.abspath(filename))

        try:
            logging.info('Reading config file "{}"...'.format(filename))

            with open(filename, 'r', encoding='utf-8') as config_file:
                self.config = yaml.safe_load(config_file)
        except IOError:
            logging.error('Failed to read config file "{}"!'.format(filename))

            self.config = {}

    def _load_dotenv(self):
        """Load environment variables from .env file if python-dotenv is available."""
        try:
            from dotenv import load_dotenv
            # Look for .env in current working directory
            env_path = Path.cwd() / '.env'
            if env_path.exists():
                logging.debug('Loading environment variables from {}'.format(env_path))
                load_dotenv(env_path)
            else:
                logging.debug('No .env file found at {}'.format(env_path))
        except ImportError:
            logging.debug('python-dotenv not installed; skipping .env file loading')
        except Exception as e:
            logging.warning('Error loading .env file: {}'.format(e))

    def get(self, path, default=None):
        # Check if this is a sensitive key and look for environment variable override
        if path in self.SENSITIVE_KEYS:
            env_var = self.SENSITIVE_KEYS[path]
            env_value = os.environ.get(env_var)
            if env_value is not None:
                logging.debug('Using environment variable {} for config key "{}"'.format(env_var, path))
                return env_value

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

            page_tiles[tuple(conf_screen_tile_pos)] = conf_tile_class_info['class'](deck=deck, hass=hass, tile_class=conf_tile_class_info, tile_info=conf_screen_tile, base_path=config.config_dir)

        pages[conf_screen_name] = page_tiles

    tile_manager = TileManager(deck, pages, base_path=config.config_dir)

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


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    config = Config('config.yaml')

    # Run main inside a managed event loop. main() will not return (it waits forever),
    # so control stays inside asyncio.run and background tasks remain active.
    asyncio.run(main(config))
