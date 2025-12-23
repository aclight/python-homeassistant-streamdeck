#   Python StreamDeck HomeAssistant Client
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

from .TileImage import TileImage
import logging

class BaseTile(object):
    def __init__(self, deck, hass=None, tile_class=None, tile_info=None, base_path=None):
        self.deck = deck
        self.hass = hass
        self.tile_class = tile_class
        self.tile_info = tile_info
        self.base_path = base_path

        self.image_tile = TileImage(deck, base_path=base_path)
        self.old_state = None

    @property
    async def state(self):
        return None

    async def get_image(self, force=True):
        state = await self.state

        if state == self.old_state and not force:
            return None

        self.old_state = state

        if self.tile_class is None:
            return self.image_tile

        format_dict = {'state': state, **self.tile_info}

        # Look up the state configuration, trying template variable substitution
        state_tile = None
        
        # First try exact match
        state_tile = self.tile_class['states'].get(state)
        
        # If no exact match, try matching against template variables
        if state_tile is None:
            for state_key, state_config in self.tile_class['states'].items():
                if state_key is not None:
                    # Apply template substitution to the state key and check if it matches
                    try:
                        substituted_key = str(state_key).format_map(format_dict)
                        if substituted_key == state:
                            state_tile = state_config
                            break
                    except (KeyError, ValueError):
                        # If format_map fails, just continue
                        continue
        
        # Fall back to None state if no match found
        if state_tile is None:
            state_tile = self.tile_class['states'].get(None) or {}

        image_tile = self.image_tile
        image_tile.color = state_tile.get('color')
        image_tile.overlay = state_tile.get('overlay', '').format_map(format_dict)
        image_tile.label = state_tile.get('label', '').format_map(format_dict)
        image_tile.label_font = state_tile.get('label_font')
        image_tile.label_size = state_tile.get('label_size')
        image_tile.value = state_tile.get('value', '').format_map(format_dict)
        image_tile.value_font = state_tile.get('value_font')
        image_tile.value_size = state_tile.get('value_size')
        image_tile.border = state_tile.get('border', '').format_map(format_dict)
        
        # Handle icons - can be a single string or list of strings
        icons = state_tile.get('icons')
        logging.debug(f"State tile icons from config: {icons}")
        if icons is not None:
            if isinstance(icons, str):
                image_tile.icons = icons.format_map(format_dict)
            elif isinstance(icons, list):
                image_tile.icons = [icon.format_map(format_dict) if isinstance(icon, str) else icon for icon in icons]
            else:
                image_tile.icons = icons

        return image_tile

    async def button_state_changed(self, tile_manager, state):
        pass


class HassTile(BaseTile):
    def __init__(self, deck, hass, tile_class, tile_info, base_path=None):
        super().__init__(deck, hass, tile_class, tile_info, base_path=base_path)

    @property
    async def state(self):
        hass_state = await self.hass.get_state(self.tile_info['entity_id'])
        return hass_state.get('state')

    async def button_state_changed(self, tile_manager, state):
        if not state:
            return

        if self.tile_class.get('action') is not None:
            action = self.tile_class.get('action').split('/')
            if len(action) == 1:
                domain = 'homeassistant'
                service = action[0]
            else:
                domain = action[0]
                service = action[1]

            data = None
            if self.tile_info.get('data') is not None:
                data = self.tile_info.get('data')

            await self.hass.set_state(domain=domain, service=service, entity_id=self.tile_info['entity_id'], data=data)


class PageTile(BaseTile):
    def __init__(self, deck, hass, tile_class, tile_info, base_path=None):
        super().__init__(deck, hass, tile_class, tile_info, base_path=base_path)

    async def button_state_changed(self, tile_manager, state):
        if not state:
            return

        page_name = self.tile_info.get('page')
        await tile_manager.set_deck_page(page_name)

class PercentageControlTile(BaseTile):
    """Tile for controlling any percentage-based value (0-100) in Home Assistant.
    
    Works with input_number, number entities, or any entity with numeric state.
    Can be used for brightness, volume, fan speed, or any other 0-100 percentage value.
    """
    
    def __init__(self, deck, hass, tile_class, tile_info, base_path=None):
        super().__init__(deck, hass, tile_class, tile_info, base_path=base_path)

    @property
    async def state(self):
        """Get current percentage value as state for display."""
        entity_id = self.tile_info.get('entity_id')
        if not entity_id:
            return 'unknown'
        
        hass_state = await self.hass.get_state(entity_id)
        if not hass_state:
            return 'unknown'
        
        try:
            value = int(float(hass_state.get('state', '0')))
            return str(value)
        except (ValueError, TypeError):
            return 'unknown'

    async def button_state_changed(self, tile_manager, state):
        """Handle button press to increase/decrease the percentage value.
        
        Use positive increment to increase, negative to decrease.
        """
        if not state:
            return
        
        entity_id = self.tile_info.get('entity_id')
        if not entity_id:
            logging.warning('PercentageControlTile: No entity_id configured')
            return
        
        # Allow action to be overridden per-tile, fallback to tile_class action
        action = (self.tile_info.get('action') or self.tile_class.get('action', '')).lower()
        increment = float(self.tile_info.get('increment', 10))

        # Get current value
        try:
            current_state = await self.hass.get_state(entity_id)
            if not current_state:
                logging.warning(f'PercentageControlTile: Entity {entity_id} not found')
                return
            logging.debug(f'PercentageControlTile: Current state of {entity_id} is {current_state}')    
            current_attributes = current_state.get('attributes', {})
            min_value = float(current_attributes.get('min', 0))
            max_value = float(current_attributes.get('max', 100))
            logging.debug(f'PercentageControlTile: Min is {min_value}, Max is {max_value}')

            current_value = float(current_state.get('state', '0'))
            
            # Calculate new value by applying increment (positive or negative)
            new_value = current_value + increment
            
            # Clamp to configured range
            new_value = max(min_value, min(new_value, max_value))
            data = {'value': new_value}

            # Determine the correct domain/service based on the action or entity type
            if 'number/' in action and 'input_number' not in action:
                # Use number domain for newer number helper
                await self.hass.set_state(domain='number', service='set_value', entity_id=entity_id, data=data)
            else:
                # Default to input_number for backward compatibility
                await self.hass.set_state(domain='input_number', service='set_value', entity_id=entity_id, data=data)
        
            logging.debug(f'PercentageControlTile: Changed {entity_id} from {current_value} to {new_value}')    
        except (ValueError, TypeError) as e:
            logging.warning(f'PercentageControlTile: Could not parse value: {e}')
            return
            
