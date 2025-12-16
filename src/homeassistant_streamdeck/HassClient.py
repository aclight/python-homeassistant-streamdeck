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


class BrightnessController:
    """Controls StreamDeck brightness based on a Home Assistant entity value.
    
    Monitors a numeric entity (0-100) and applies brightness changes to the
    StreamDeck. Only updates brightness when the screen is on.
    """
    
    def __init__(self, deck, hass, default_brightness=20):
        self.deck = deck
        self.hass = hass
        self.entity_id = None
        self.current_brightness = default_brightness

    async def start(self, entity_id):
        """Start monitoring the brightness entity."""
        if not entity_id:
            return
        
        self.entity_id = entity_id
        
        # Subscribe to state changes for the entity
        await self.hass.subscribe_to_event('state_changed', self._handle_state_changed)
        
        # Get current entity state and apply it
        current_state = await self.hass.get_state(self.entity_id)
        if current_state:
            state_value = current_state.get('state')
            await self._apply_brightness(state_value)

    async def _handle_state_changed(self, data):
        """Handle state changes from Home Assistant."""
        entity_id = data.get('entity_id')
        if entity_id != self.entity_id:
            return
        
        new_state = data.get('new_state')
        if new_state is None:
            return
        
        state_value = new_state.get('state')
        await self._apply_brightness(state_value)

    async def _apply_brightness(self, state_value):
        """Parse state value and apply brightness to the deck."""
        try:
            # Try to convert to float/int
            brightness_value = float(state_value)
            brightness_int = int(brightness_value)
            
            # Clamp to 0-100 range
            if brightness_int < 0:
                brightness_int = 0
            elif brightness_int > 100:
                brightness_int = 100
            
            self.current_brightness = brightness_int
            
            # Update the deck brightness immediately
            self.deck.set_brightness(brightness_int)
            logging.debug(f"BrightnessController: Set brightness to {brightness_int}%")
        except (ValueError, TypeError) as e:
            logging.warning(f"BrightnessController: Could not parse brightness value '{state_value}': {e}")

class EntityBasedScreensaver:
    """Screensaver controlled by a Home Assistant entity state.
    
    When the monitored entity is 'off', the screensaver activates (screen dark).
    When 'on', the screen is active at normal brightness.
    Button presses wake the screen briefly, with auto-sleep after timeout.
    
    Handles the tricky case where a power button press causes the entity to turn 'off'
    before the button is released, which would otherwise wake the screen immediately.
    """
    
    def __init__(self, deck, hass, brightness_controller=None):
        self.deck = deck
        self.hass = hass
        self.brightness_controller = brightness_controller
        self.entity_id = None
        self.wake_timeout = 20
        self.brightness = 20
        self.callback = None
        self.on = False
        self.steps = 0
        self.in_wake_state = False
        self.entity_state = 'on'
        self.last_button_press_time = 0
        self.button_press_key = None
        self.suppress_wake_until_release = False
        
        deck.set_key_callback_async(self._handle_button_press)

    async def start(self, entity_id, brightness, callback, wake_timeout=5):
        """Start monitoring the entity for screensaver state."""
        self.entity_id = entity_id
        self.brightness = brightness
        self.callback = callback
        self.wake_timeout = wake_timeout
        
        # Subscribe to state changes for the entity
        await self.hass.subscribe_to_event('state_changed', self._handle_state_changed)
        
        # Get current entity state and apply it
        current_state = await self.hass.get_state(self.entity_id)
        if current_state:
            await self._apply_entity_state(current_state.get('state'))
        
        # Start the update loop
        asyncio.create_task(self._loop())

    async def _handle_state_changed(self, data):
        """Handle state changes from Home Assistant."""
        entity_id = data.get('entity_id')
        if entity_id != self.entity_id:
            return
        
        new_state = data.get('new_state')
        if new_state is None:
            return
        
        state = new_state.get('state')
        await self._apply_entity_state(state)

    async def _apply_entity_state(self, state):
        """Apply the entity state to the screensaver."""
        self.entity_state = state
        
        if state == 'on':
            # Display should be on
            if not self.on:
                await self._set_on()
        else:
            # Display should be off (screensaver mode)
            # Apply off state unless we're in an active wake state from a button press
            if not self.in_wake_state:
                await self._set_off()
            # If display was turned off by entity, we should suppress wake on button release
            # (in case the button press caused the entity change)
            if self.on or self.in_wake_state:
                self.suppress_wake_until_release = True

    async def _loop(self):
        """Main loop to handle wake timeout."""
        while True:
            await asyncio.sleep(0.1)
            
            if self.in_wake_state:
                # Check if wake timeout has elapsed
                elapsed = asyncio.get_event_loop().time() - self.last_button_press_time
                if elapsed >= self.wake_timeout:
                    # Return to screensaver if entity is off
                    if self.entity_state != 'on':
                        await self._set_off()
                    self.in_wake_state = False

    async def _set_on(self):
        """Turn on the screen."""
        # Use brightness from controller if available, otherwise use default
        brightness = self.brightness
        if self.brightness_controller and self.brightness_controller.entity_id:
            brightness = self.brightness_controller.current_brightness
        
        self.deck.set_brightness(brightness)
        self.on = True
        logging.debug(f"EntityBasedScreensaver: Screen ON (brightness: {brightness}%)")

    async def _set_off(self):
        """Turn off the screen (screensaver mode)."""
        self.deck.set_brightness(0)
        self.on = False
        self.in_wake_state = False
        logging.debug(f"EntityBasedScreensaver: Screen OFF")

    async def _handle_button_press(self, deck, key, state):
        """Handle button presses.
        
        state=True: Button pressed
        state=False: Button released
        """
        # Record button press time
        self.last_button_press_time = asyncio.get_event_loop().time()
        
        if state:
            # Button pressed
            self.button_press_key = key
            self.suppress_wake_until_release = False
            
            # If screen is off and entity says it should be off, wake it up
            if not self.on and self.entity_state != 'on':
                await self._set_on()
                self.in_wake_state = True
                logging.debug(f"EntityBasedScreensaver: Button press woke screen")
                return
        else:
            # Button released
            if self.suppress_wake_until_release:
                # Entity turned off (probably due to this button press), don't process
                self.suppress_wake_until_release = False
                logging.debug(f"EntityBasedScreensaver: Suppressing wake on release due to entity change")
                return
            
            # If screen is off and entity says it should be off, wake it on release
            if not self.on and self.entity_state != 'on':
                await self._set_on()
                self.in_wake_state = True
                logging.debug(f"EntityBasedScreensaver: Button release woke screen")
                return
        
        # Button pressed/released while screen is on - call original callback
        if self.on:
            await self.callback(deck, key, state)


async def main(config):
  
    conf_deck_brightness = config.get('streamdeck/brightness', 20)
    conf_deck_screensaver = config.get('streamdeck/screensaver', 0)
    conf_screensaver_entity = config.get('streamdeck/screensaver_entity')
    conf_screensaver_wake_timeout = config.get('streamdeck/screensaver_wake_timeout', 5)
    conf_brightness_entity = config.get('streamdeck/brightness_entity')
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

    # Initialize brightness controller if configured
    brightness_controller = BrightnessController(deck=deck, hass=hass, default_brightness=conf_deck_brightness)
    if conf_brightness_entity:
        logging.info(f"Using brightness control via entity: {conf_brightness_entity}")
        await brightness_controller.start(conf_brightness_entity)

    # Initialize screensaver - use entity-based if configured, otherwise use timer-based
    if conf_screensaver_entity:
        logging.info(f"Using entity-based screensaver, monitoring entity: {conf_screensaver_entity}")
        screensaver = EntityBasedScreensaver(deck=deck, hass=hass, brightness_controller=brightness_controller)
        await screensaver.start(
            entity_id=conf_screensaver_entity,
            brightness=conf_deck_brightness,
            callback=steamdeck_key_state_changed,
            wake_timeout=conf_screensaver_wake_timeout
        )
    else:
        logging.info("Using timer-based screensaver")
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
            # Reset the StreamDeck device and close it cleanly
            deck.reset()
            deck.close()
        except Exception:
            logging.exception("Error closing StreamDeck")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    config = Config('config.yaml')

    # Run main inside a managed event loop. main() will not return (it waits forever),
    # so control stays inside asyncio.run and background tasks remain active.
    asyncio.run(main(config))
