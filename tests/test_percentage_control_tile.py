"""Tests for PercentageControlTile class."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_deck():
    """Create a mock StreamDeck device."""
    deck = MagicMock()
    return deck


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistantWS client."""
    hass = AsyncMock()
    hass.get_state = AsyncMock()
    hass.set_state = AsyncMock()
    return hass


@pytest.fixture
def tile_class_config():
    """Create a tile class configuration."""
    return {
        'states': {None: {}},
        'action': 'increase'
    }


@pytest.fixture
def percentage_tile(mock_deck, mock_hass, tile_class_config):
    """Create a PercentageControlTile instance for testing."""
    from Tile.Tile import PercentageControlTile
    
    tile_info = {
        'entity_id': 'input_number.test_value',
        'increment': 10,
        'name': 'Test Control'
    }
    
    return PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )


@pytest.mark.asyncio
async def test_percentage_tile_state_retrieval(percentage_tile, mock_hass):
    """Test getting the current state for display."""
    mock_hass.get_state.return_value = {'state': '45'}
    
    state = await percentage_tile.state
    
    assert state == '45'


@pytest.mark.asyncio
async def test_percentage_tile_state_no_entity(mock_deck, mock_hass, tile_class_config):
    """Test state when no entity_id is configured."""
    from Tile.Tile import PercentageControlTile
    
    tile_info = {'name': 'Test Control'}  # No entity_id
    tile = PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )
    
    state = await tile.state
    assert state == 'unknown'


@pytest.mark.asyncio
async def test_percentage_tile_state_unknown_entity(percentage_tile, mock_hass):
    """Test state when entity is not found."""
    mock_hass.get_state.return_value = None
    
    state = await percentage_tile.state
    
    assert state == 'unknown'


@pytest.mark.asyncio
async def test_percentage_tile_state_invalid_value(percentage_tile, mock_hass):
    """Test state with invalid numeric value."""
    mock_hass.get_state.return_value = {'state': 'invalid'}
    
    state = await percentage_tile.state
    
    assert state == 'unknown'


@pytest.mark.asyncio
async def test_percentage_tile_state_float_conversion(percentage_tile, mock_hass):
    """Test state converts float to int."""
    mock_hass.get_state.return_value = {'state': '42.7'}
    
    state = await percentage_tile.state
    
    assert state == '42'


@pytest.mark.asyncio
async def test_percentage_tile_increase_action(percentage_tile, mock_hass):
    """Test increasing percentage value."""
    mock_hass.get_state.return_value = {
        'state': '50',
        'attributes': {'min': 0, 'max': 100}
    }
    
    # Button pressed (state=True)
    await percentage_tile.button_state_changed(None, True)
    
    # Should call set_state with value 60 (50 + 10)
    mock_hass.set_state.assert_called_once()
    call_args = mock_hass.set_state.call_args
    assert call_args[1]['data']['value'] == 60


@pytest.mark.asyncio
async def test_percentage_tile_decrease_action(mock_deck, mock_hass, tile_class_config):
    """Test decreasing percentage value."""
    from Tile.Tile import PercentageControlTile
    
    tile_class_config['action'] = 'decrease'
    tile_info = {
        'entity_id': 'input_number.test_value',
        'increment': 10,
    }
    
    tile = PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )
    
    mock_hass.get_state.return_value = {
        'state': '50',
        'attributes': {'min': 0, 'max': 100}
    }
    
    await tile.button_state_changed(None, True)
    
    # Should call set_state with value 40 (50 - 10)
    call_args = mock_hass.set_state.call_args
    assert call_args[1]['data']['value'] == 40


@pytest.mark.asyncio
async def test_percentage_tile_clamp_to_max(percentage_tile, mock_hass):
    """Test that increase is clamped to max value."""
    mock_hass.get_state.return_value = {
        'state': '95',
        'attributes': {'min': 0, 'max': 100}
    }
    
    await percentage_tile.button_state_changed(None, True)
    
    # Should clamp to 100 instead of 105
    call_args = mock_hass.set_state.call_args
    assert call_args[1]['data']['value'] == 100


@pytest.mark.asyncio
async def test_percentage_tile_clamp_to_min(mock_deck, mock_hass, tile_class_config):
    """Test that decrease is clamped to min value."""
    from Tile.Tile import PercentageControlTile
    
    tile_class_config['action'] = 'decrease'
    tile_info = {
        'entity_id': 'input_number.test_value',
        'increment': 10,
    }
    
    tile = PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )
    
    mock_hass.get_state.return_value = {
        'state': '5',
        'attributes': {'min': 0, 'max': 100}
    }
    
    await tile.button_state_changed(None, True)
    
    # Should clamp to 0 instead of -5
    call_args = mock_hass.set_state.call_args
    assert call_args[1]['data']['value'] == 0


@pytest.mark.asyncio
async def test_percentage_tile_custom_min_max(mock_deck, mock_hass, tile_class_config):
    """Test with custom min/max range."""
    from Tile.Tile import PercentageControlTile
    
    tile_info = {
        'entity_id': 'input_number.fan_speed',
        'increment': 5,
    }
    
    tile = PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )
    
    # Entity configured with 10-50 range
    mock_hass.get_state.return_value = {
        'state': '30',
        'attributes': {'min': 10, 'max': 50}
    }
    
    await tile.button_state_changed(None, True)
    
    # Should increase to 35, but clamp to max 50
    call_args = mock_hass.set_state.call_args
    assert call_args[1]['data']['value'] == 35


@pytest.mark.asyncio
async def test_percentage_tile_default_min_max(mock_deck, mock_hass, tile_class_config):
    """Test default min/max when attributes missing."""
    from Tile.Tile import PercentageControlTile
    
    tile_info = {
        'entity_id': 'input_number.test_value',
        'increment': 20,
    }
    
    tile = PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )
    
    # No attributes provided
    mock_hass.get_state.return_value = {'state': '80'}
    
    await tile.button_state_changed(None, True)
    
    # Should use default 0-100 range
    call_args = mock_hass.set_state.call_args
    assert call_args[1]['data']['value'] == 100  # Clamped to default max


@pytest.mark.asyncio
async def test_percentage_tile_button_released_ignored(percentage_tile, mock_hass):
    """Test that button release (state=False) is ignored."""
    mock_hass.get_state.return_value = {
        'state': '50',
        'attributes': {'min': 0, 'max': 100}
    }
    
    # Button released (state=False)
    await percentage_tile.button_state_changed(None, False)
    
    # Should not call set_state
    mock_hass.set_state.assert_not_called()


@pytest.mark.asyncio
async def test_percentage_tile_missing_entity_id(mock_deck, mock_hass, tile_class_config):
    """Test with missing entity_id configuration."""
    from Tile.Tile import PercentageControlTile
    
    tile_info = {'increment': 10}  # No entity_id
    
    tile = PercentageControlTile(
        deck=mock_deck,
        hass=mock_hass,
        tile_class=tile_class_config,
        tile_info=tile_info
    )
    
    await tile.button_state_changed(None, True)
    
    # Should not call set_state
    mock_hass.set_state.assert_not_called()
