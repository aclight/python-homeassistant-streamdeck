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


class ConnectionMonitor:
    """Monitors Home Assistant connection state and handles reconnection attempts."""
    
    def __init__(self, hass, tile_manager, reconnect_interval=5, reconnect_retries=3):
        self.hass = hass
        self.tile_manager = tile_manager
        self.reconnect_interval = reconnect_interval
        self.reconnect_retries = reconnect_retries
        self.is_connected = False
        self.api_password = None
        self.api_token = None
        self.screensaver = None
        
        # Register for connection state changes
        hass.register_connection_callback(self._on_connection_state_changed)

    async def set_credentials(self, api_password=None, api_token=None):
        """Store credentials for reconnection attempts."""
        self.api_password = api_password
        self.api_token = api_token

    def set_screensaver(self, screensaver):
        """Set the screensaver instance to control on connection changes."""
        self.screensaver = screensaver

    async def _on_connection_state_changed(self, connected):
        """Callback when connection state changes."""
        was_connected = self.is_connected
        self.is_connected = connected
        logging.info(f"ConnectionMonitor: Connection state changed: {was_connected} -> {connected}")
        
        # Update tile manager connection state for display purposes
        await self.tile_manager.update_page(force_redraw=True)
        
        if connected and not was_connected:
            logging.info("Home Assistant connection restored")
            # Restore screensaver to normal state if it was forced dark
            if self.screensaver and hasattr(self.screensaver, '_restore_after_disconnect'):
                logging.info("ConnectionMonitor: Calling screensaver._restore_after_disconnect()")
                await self.screensaver._restore_after_disconnect()
        elif not connected and was_connected:
            logging.warning("Lost connection to Home Assistant")
            # Force screensaver to dark mode when disconnected
            if self.screensaver and hasattr(self.screensaver, '_activate_on_disconnect'):
                logging.warning("ConnectionMonitor: Calling screensaver._activate_on_disconnect()")
                await self.screensaver._activate_on_disconnect()

    async def monitor(self):
        """Background task to monitor connection and attempt reconnection."""
        while True:
            if not self.is_connected:
                await self._attempt_reconnect()
            await asyncio.sleep(self.reconnect_interval)

    async def _attempt_reconnect(self):
        """Attempt to reconnect to Home Assistant."""
        for attempt in range(1, self.reconnect_retries + 1):
            try:
                logging.info(f"Attempting to reconnect to Home Assistant (attempt {attempt}/{self.reconnect_retries})...")
                await self.hass.connect(api_password=self.api_password, api_token=self.api_token)
                return  # Connection successful
            except Exception as e:
                if attempt < self.reconnect_retries:
                    logging.debug(f"Reconnection attempt {attempt} failed: {e}")
                    await asyncio.sleep(self.reconnect_interval)
                else:
                    logging.warning(f"Failed to reconnect after {self.reconnect_retries} attempts: {e}")


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
        
        # Track disconnection state
        self.hass_disconnected = False
        self.state_before_disconnect = 'on'
        
        deck.set_key_callback_async(self._handle_button_press)

    async def start(self, entity_id, brightness, callback, wake_timeout=5):
        """Start monitoring the entity for screensaver state."""
        self.entity_id = entity_id
        self.brightness = brightness
        self.callback = callback
        self.wake_timeout = wake_timeout
        
        logging.debug(f"EntityBasedScreensaver: Starting with entity {entity_id}, brightness {brightness}")
        
        # Subscribe to state changes for the entity
        try:
            await self.hass.subscribe_to_event('state_changed', self._handle_state_changed)
        except Exception as e:
            logging.debug(f"EntityBasedScreensaver: Could not subscribe to events yet: {e}")
        
        # Get current entity state and apply it
        try:
            current_state = await self.hass.get_state(self.entity_id)
            if current_state:
                await self._apply_entity_state(current_state.get('state'))
                logging.debug(f"EntityBasedScreensaver: Applied initial state: {current_state.get('state')}")
        except Exception as e:
            logging.debug(f"EntityBasedScreensaver: Could not get initial entity state: {e}")
        
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
        
        try:
            self.deck.set_brightness(brightness)
            self.on = True
            logging.debug(f"EntityBasedScreensaver: Screen ON (brightness: {brightness}%)")
        except Exception as e:
            logging.warning(f"EntityBasedScreensaver: Could not set screen brightness: {e}")
            self.on = True  # Mark as on even if we couldn't set brightness

    async def _set_off(self):
        """Turn off the screen (screensaver mode)."""
        try:
            self.deck.set_brightness(0)
            self.on = False
            self.in_wake_state = False
            logging.debug(f"EntityBasedScreensaver: Screen OFF")
        except Exception as e:
            logging.warning(f"EntityBasedScreensaver: Could not set screen brightness: {e}")
            self.on = False  # Mark as off even if we couldn't set brightness
            self.in_wake_state = False

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


    async def _activate_on_disconnect(self):
        """Activate screensaver when Home Assistant disconnects."""
        logging.info(f"EntityBasedScreensaver: _activate_on_disconnect() called (hass_disconnected={self.hass_disconnected})")
        if not self.hass_disconnected:
            self.hass_disconnected = True
            # Save the current entity state so we can restore it later
            self.state_before_disconnect = self.entity_state
            # Force dark mode
            self.entity_state = 'off'
            logging.info(f"EntityBasedScreensaver: Attempting disconnect activation (on={self.on}, in_wake_state={self.in_wake_state})")
            if not self.in_wake_state:
                logging.info("EntityBasedScreensaver: Calling _set_off()")
                await self._set_off()
            else:
                logging.warning("EntityBasedScreensaver: in_wake_state=True, skipping _set_off()")
            logging.info("EntityBasedScreensaver: Activated due to Home Assistant disconnection")
        else:
            logging.debug("EntityBasedScreensaver: Already in hass_disconnected state, skipping")

    async def _restore_after_disconnect(self):
        """Restore screensaver state after Home Assistant reconnects."""
        if self.hass_disconnected:
            self.hass_disconnected = False
            # Restore the previous entity state
            self.entity_state = self.state_before_disconnect
            # Apply the restored state
            if self.entity_state == 'on':
                if not self.on:
                    await self._set_on()
            else:
                if not self.in_wake_state:
                    await self._set_off()
            logging.info(f"EntityBasedScreensaver: Restored after Home Assistant reconnection (state: {self.entity_state})")


async def main(config):
    try:
        await _main_impl(config)
    except Exception:
        logging.exception("Fatal error in main")
        raise

async def _main_impl(config):
  
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
            
            if conf_tile_class_info is None:
                logging.error(f"Unknown tile type '{conf_screen_tile_type}' in screen '{conf_screen_name}' at position {conf_screen_tile_pos}")
                continue

            page_tiles[tuple(conf_screen_tile_pos)] = conf_tile_class_info['class'](deck=deck, hass=hass, tile_class=conf_tile_class_info, tile_info=conf_screen_tile, base_path=config.config_dir)

        pages[conf_screen_name] = page_tiles

    tile_manager = TileManager(deck, pages, base_path=config.config_dir)

    async def hass_state_changed(data):
        await tile_manager.update_page(force_redraw=False)

    async def steamdeck_key_state_changed(deck, key, state):
        await tile_manager.button_state_changed(key, state)

    # enable logging-level and loop-level debug settings if requested in config
    if config.get('debug'):
        logging.getLogger().setLevel(logging.DEBUG)
        logging.info('Debug enabled')
        loop = asyncio.get_running_loop()
        loop.set_debug(True)
        loop.slow_callback_duration = 0.15

    # Open the StreamDeck first (before attempting to connect to Home Assistant)
    # Try to open, but don't block startup if device isn't available
    async def open_deck_with_retry():
        nonlocal deck
        
        # Initial delay to allow device to fully reset after service restart
        logging.info("Waiting for StreamDeck device to be ready...")
        await asyncio.sleep(1)
        
        max_retries = 5
        retry_interval = 1
        for attempt in range(1, max_retries + 1):
            try:
                logging.debug(f"StreamDeck open attempt {attempt}/{max_retries}")
                deck.open()
                logging.info("StreamDeck device opened successfully")
                
                # Reset the device to a known state
                try:
                    logging.debug("Resetting StreamDeck device")
                    deck.reset()
                    await asyncio.sleep(0.5)  # Brief pause after reset
                except Exception as e:
                    logging.warning(f"Failed to reset StreamDeck: {e}")

                try:
                    # Ensure the device is awake and at a visible brightness (do this after reset)
                    deck.set_brightness(conf_deck_brightness)
                    logging.debug(f"Set initial StreamDeck brightness to {conf_deck_brightness}%")
                except Exception as e:
                    logging.warning(f"Failed to set initial StreamDeck brightness: {e}")
                
                logging.info("StreamDeck device is ready")
                return True
            except Exception as e:
                if attempt < max_retries:
                    # If we get a device error, try re-enumerating devices on later attempts
                    if "device" in str(e).lower() or "hid" in str(e).lower():
                        if attempt > 2:  # After second failure, try re-enumerating
                            logging.debug("Attempting to re-enumerate StreamDeck devices...")
                            try:
                                new_decks = StreamDeck.DeviceManager().enumerate()
                                if new_decks:
                                    deck = new_decks[0]
                                    logging.info("Re-enumerated StreamDeck devices, found device")
                                else:
                                    logging.warning("Re-enumeration found no devices")
                            except Exception as enum_error:
                                logging.warning(f"Failed to re-enumerate devices: {enum_error}")
                    
                    wait_time = retry_interval * attempt  # Exponential backoff
                    logging.warning(f"Failed to open StreamDeck (attempt {attempt}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    logging.error(f"Failed to open StreamDeck after {max_retries} attempts: {e}")
                    logging.info("StreamDeck device not available. Service will continue running.")
                    return False
    
    deck_opened = await open_deck_with_retry()

    # Set up the connection monitor before attempting connection
    connection_monitor = ConnectionMonitor(hass, tile_manager, reconnect_interval=5, reconnect_retries=3)
    await connection_monitor.set_credentials(api_password=conf_hass_pw, api_token=conf_hass_token)
    
    # Start the connection monitoring task (it will handle reconnection attempts)
    asyncio.create_task(connection_monitor.monitor())

    # Attempt initial connection
    logging.info("Connecting to %s:%s...", conf_hass_host, conf_hass_port)
    try:
        await hass.connect(api_password=conf_hass_pw, api_token=conf_hass_token)
    except Exception as e:
        logging.warning(f"Failed to connect to Home Assistant on startup: {e}")
        logging.info("Will attempt to reconnect in background. StreamDeck is ready and waiting...")

    # Initialize brightness controller if configured
    brightness_controller = BrightnessController(deck=deck, hass=hass, default_brightness=conf_deck_brightness)
    if conf_brightness_entity:
        logging.info(f"Using brightness control via entity: {conf_brightness_entity}")
        # Try to start, but don't fail if Home Assistant isn't connected yet
        try:
            await brightness_controller.start(conf_brightness_entity)
        except Exception as e:
            logging.debug(f"Could not start brightness controller yet: {e}")

    # Initialize screensaver - use entity-based if configured, otherwise use timer-based
    if conf_screensaver_entity:
        logging.info(f"Using entity-based screensaver, monitoring entity: {conf_screensaver_entity}")
        screensaver = EntityBasedScreensaver(deck=deck, hass=hass, brightness_controller=brightness_controller)
        # Try to start, but don't fail if Home Assistant isn't connected yet
        try:
            await screensaver.start(
                entity_id=conf_screensaver_entity,
                brightness=conf_deck_brightness,
                callback=steamdeck_key_state_changed,
                wake_timeout=conf_screensaver_wake_timeout
            )
        except Exception as e:
            logging.debug(f"Could not start screensaver yet: {e}")
        
        # Register screensaver with connection monitor to activate/deactivate on disconnect
        connection_monitor.set_screensaver(screensaver)
    else:
        logging.info("Using timer-based screensaver")
        screensaver = ScreenSaver(deck=deck)
        await screensaver.start(brightness=conf_deck_brightness, callback=steamdeck_key_state_changed, timeout=conf_deck_screensaver)
        
        # For timer-based screensaver, activate it on disconnect (set brightness to 0)
        # by creating a simple wrapper
        class TimerScreensaverWrapper:
            def __init__(self, ss):
                self.screensaver = ss
            async def _activate_on_disconnect(self):
                await self.screensaver._set_off()
                logging.info("TimerScreensaver: Activated due to Home Assistant disconnection")
            async def _restore_after_disconnect(self):
                # Timer screensaver will handle its own timeout, just restore brightness
                await self.screensaver._set_on()
                logging.info("TimerScreensaver: Restored after Home Assistant reconnection")
        
        connection_monitor.set_screensaver(TimerScreensaverWrapper(screensaver))

    # Set the initial page (this will work even if Home Assistant isn't connected)
    await tile_manager.set_deck_page(None)
    
    # If Home Assistant is not connected at startup, set disconnected state
    if not hass.is_connected():
        logging.info("Home Assistant is not connected at startup. Showing disconnected state.")
        tile_manager.is_connected = False
        # Redraw the page with gray overlay to show disconnected
        await tile_manager.update_page(force_redraw=True)
        # Also activate screensaver if available
        if hasattr(screensaver, '_activate_on_disconnect'):
            await screensaver._activate_on_disconnect()
    else:
        tile_manager.is_connected = True
    
    # Subscribe to state changes (will work once Home Assistant is connected)
    if hass.is_connected():
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
            # Properly close the StreamDeck device to release USB resources
            if deck:
                try:
                    logging.debug("Turning off StreamDeck brightness")
                    deck.set_brightness(0)
                except Exception:
                    logging.debug("Could not turn off StreamDeck brightness")
                    
                try:
                    logging.debug("Resetting StreamDeck device")
                    deck.reset()
                except Exception:
                    logging.debug("Could not reset StreamDeck device")
                    
                try:
                    logging.debug("Closing StreamDeck device")
                    deck.close()
                    logging.info("StreamDeck device closed cleanly")
                except Exception as e:
                    logging.debug(f"Could not close StreamDeck device: {e}")
        except Exception:
            logging.exception("Error closing StreamDeck")


if __name__ == '__main__':
    config = Config('config.yaml')
    
    # Set logging level based on config debug flag
    log_level = logging.DEBUG if config.get('debug') else logging.INFO
    logging.basicConfig(level=log_level)

    # Run main inside a managed event loop. main() will not return (it waits forever),
    # so control stays inside asyncio.run and background tasks remain active.
    asyncio.run(main(config))
