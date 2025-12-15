"""Tests for BrightnessController class."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.fixture
def mock_deck():
    """Create a mock StreamDeck device."""
    deck = MagicMock()
    deck.set_brightness = MagicMock()
    return deck


@pytest.fixture
def mock_hass():
    """Create a mock HomeAssistantWS client."""
    hass = AsyncMock()
    hass.subscribe_to_event = AsyncMock()
    hass.get_state = AsyncMock()
    return hass


@pytest.fixture
def brightness_controller(mock_deck, mock_hass):
    """Create a BrightnessController instance for testing."""
    from homeassistant_streamdeck.HassClient import BrightnessController
    
    return BrightnessController(deck=mock_deck, hass=mock_hass, default_brightness=50)


@pytest.mark.asyncio
async def test_brightness_controller_init(mock_deck, mock_hass):
    """Test BrightnessController initialization."""
    from homeassistant_streamdeck.HassClient import BrightnessController
    
    controller = BrightnessController(deck=mock_deck, hass=mock_hass, default_brightness=75)
    assert controller.current_brightness == 75
    assert controller.entity_id is None


@pytest.mark.asyncio
async def test_brightness_controller_start_no_entity(mock_deck, mock_hass):
    """Test start with no entity configured."""
    from homeassistant_streamdeck.HassClient import BrightnessController
    
    controller = BrightnessController(deck=mock_deck, hass=mock_hass, default_brightness=50)
    await controller.start(None)
    
    # Should return early without subscribing
    mock_hass.subscribe_to_event.assert_not_called()


@pytest.mark.asyncio
async def test_brightness_controller_apply_valid_value(brightness_controller, mock_deck):
    """Test applying a valid brightness value."""
    await brightness_controller._apply_brightness(75)
    
    assert brightness_controller.current_brightness == 75
    mock_deck.set_brightness.assert_called_once_with(75)


@pytest.mark.asyncio
async def test_brightness_controller_apply_clamps_low(brightness_controller, mock_deck):
    """Test that values below 0 are clamped."""
    await brightness_controller._apply_brightness(-10)
    
    assert brightness_controller.current_brightness == 0
    mock_deck.set_brightness.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_brightness_controller_apply_clamps_high(brightness_controller, mock_deck):
    """Test that values above 100 are clamped."""
    await brightness_controller._apply_brightness(150)
    
    assert brightness_controller.current_brightness == 100
    mock_deck.set_brightness.assert_called_once_with(100)


@pytest.mark.asyncio
async def test_brightness_controller_apply_float_conversion(brightness_controller, mock_deck):
    """Test that float strings are converted to int."""
    await brightness_controller._apply_brightness("42.7")
    
    assert brightness_controller.current_brightness == 42
    mock_deck.set_brightness.assert_called_once_with(42)


@pytest.mark.asyncio
async def test_brightness_controller_apply_invalid_value(brightness_controller, mock_deck):
    """Test that invalid values are handled gracefully."""
    await brightness_controller._apply_brightness("invalid")
    
    # Should log warning but not crash, brightness unchanged
    mock_deck.set_brightness.assert_not_called()
    assert brightness_controller.current_brightness == 50  # Unchanged


@pytest.mark.asyncio
async def test_brightness_controller_start_with_entity(brightness_controller, mock_hass):
    """Test start subscribes to entity changes."""
    mock_hass.get_state.return_value = {'state': '60'}
    
    await brightness_controller.start('input_number.test_brightness')
    
    assert brightness_controller.entity_id == 'input_number.test_brightness'
    mock_hass.subscribe_to_event.assert_called_once()


@pytest.mark.asyncio
async def test_brightness_controller_handle_state_change(brightness_controller, mock_deck):
    """Test handling state change events."""
    brightness_controller.entity_id = 'input_number.test'
    
    data = {
        'entity_id': 'input_number.test',
        'new_state': {'state': '85'}
    }
    
    await brightness_controller._handle_state_changed(data)
    
    assert brightness_controller.current_brightness == 85
    mock_deck.set_brightness.assert_called_once_with(85)


@pytest.mark.asyncio
async def test_brightness_controller_ignore_other_entities(brightness_controller, mock_deck):
    """Test that state changes for other entities are ignored."""
    brightness_controller.entity_id = 'input_number.test'
    
    data = {
        'entity_id': 'input_number.other',
        'new_state': {'state': '50'}
    }
    
    await brightness_controller._handle_state_changed(data)
    
    # Should not update brightness
    mock_deck.set_brightness.assert_not_called()
    assert brightness_controller.current_brightness == 50  # Unchanged (default)
