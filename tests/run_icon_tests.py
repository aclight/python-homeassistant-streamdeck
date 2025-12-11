"""Simple test runner for icon rendering tests (pytest-free)."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from PIL import Image
import io
from unittest.mock import Mock, patch
from Tile.TileImage import TileImage


class DummyDeck:
    """Dummy deck object for testing without hardware dependencies."""
    def __init__(self):
        self.key_count = 15
        self.key_rows = 3
        self.key_cols = 5

    def __getattr__(self, name):
        def _missing(*a, **k):
            return None
        return _missing


def test_parse_hex_color_6digit():
    """Test parsing 6-digit hex color."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    color = ti._parse_color('#FF0000')
    assert color == (255, 0, 0), f"Expected (255, 0, 0), got {color}"
    
    color = ti._parse_color('#00FF00')
    assert color == (0, 255, 0), f"Expected (0, 255, 0), got {color}"
    
    color = ti._parse_color('#0000FF')
    assert color == (0, 0, 255), f"Expected (0, 0, 255), got {color}"
    print("✓ test_parse_hex_color_6digit passed")


def test_parse_hex_color_3digit():
    """Test parsing 3-digit hex color shorthand."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    color = ti._parse_color('#F00')
    assert color == (255, 0, 0), f"Expected (255, 0, 0), got {color}"
    
    color = ti._parse_color('#0F0')
    assert color == (0, 255, 0), f"Expected (0, 255, 0), got {color}"
    print("✓ test_parse_hex_color_3digit passed")


def test_parse_named_colors():
    """Test parsing named colors."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    assert ti._parse_color('red') == (255, 0, 0)
    assert ti._parse_color('green') == (0, 128, 0)
    assert ti._parse_color('blue') == (0, 0, 255)
    assert ti._parse_color('white') == (255, 255, 255)
    assert ti._parse_color('black') == (0, 0, 0)
    assert ti._parse_color('yellow') == (255, 255, 0)
    print("✓ test_parse_named_colors passed")


def test_parse_invalid_color():
    """Test that invalid colors return None."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    assert ti._parse_color('invalidcolor') is None
    assert ti._parse_color('#GGGGGG') is None
    print("✓ test_parse_invalid_color passed")


def test_parse_border_solid():
    """Test parsing solid border."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    thickness, style, color = ti._parse_border('5px solid red')
    assert thickness == 5, f"Expected thickness 5, got {thickness}"
    assert style == 'solid', f"Expected style solid, got {style}"
    assert color == (255, 0, 0), f"Expected color (255, 0, 0), got {color}"
    print("✓ test_parse_border_solid passed")


def test_parse_border_dashed():
    """Test parsing dashed border."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    thickness, style, color = ti._parse_border('2px dashed #FF0000')
    assert thickness == 2
    assert style == 'dashed'
    assert color == (255, 0, 0)
    print("✓ test_parse_border_dashed passed")


def test_parse_border_dotted():
    """Test parsing dotted border."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    thickness, style, color = ti._parse_border('3px dotted blue')
    assert thickness == 3
    assert style == 'dotted'
    assert color == (0, 0, 255)
    print("✓ test_parse_border_dotted passed")


def test_parse_border_invalid():
    """Test that invalid borders return None values."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    # Missing parts
    thickness, style, color = ti._parse_border('5px solid')
    assert thickness is None
    
    # Invalid style
    thickness, style, color = ti._parse_border('5px invalid red')
    assert style is None
    
    # Invalid thickness
    thickness, style, color = ti._parse_border('invalidpx solid red')
    assert thickness is None
    print("✓ test_parse_border_invalid passed")


def test_icons_property_setter_string():
    """Test setting icons as string."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    ti.icons = 'heart'
    assert ti.icons == 'heart'
    print("✓ test_icons_property_setter_string passed")


def test_icons_property_setter_list():
    """Test setting icons as list."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    icon_list = ['heart', 'star']
    ti.icons = icon_list
    assert ti.icons == icon_list
    print("✓ test_icons_property_setter_list passed")


def test_icons_property_clears_cache():
    """Test that setting icons clears the pixel cache."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    # Simulate cached pixels
    ti._pixels = 'some_cached_data'
    
    # Setting icons should clear cache
    ti.icons = 'heart'
    assert ti._pixels is None
    print("✓ test_icons_property_clears_cache passed")


def test_public_attribute_assignment():
    """Test that public attributes can be assigned and read."""
    deck = DummyDeck()
    ti = TileImage(deck)
    
    # Test all public attributes
    ti.color = (255, 0, 0)
    assert ti.color == (255, 0, 0)
    
    ti.overlay = 'test.png'
    assert ti.overlay == 'test.png'
    
    ti.label = 'Test Label'
    assert ti.label == 'Test Label'
    
    ti.label_font = 'Roboto-Bold.ttf'
    assert ti.label_font == 'Roboto-Bold.ttf'
    
    ti.label_size = 12
    assert ti.label_size == 12
    
    ti.value = '42'
    assert ti.value == '42'
    
    ti.value_font = 'Roboto-Light.ttf'
    assert ti.value_font == 'Roboto-Light.ttf'
    
    ti.value_size = 18
    assert ti.value_size == 18
    
    ti.border = '2px solid red'
    assert ti.border == '2px solid red'
    
    ti.icons = 'heart'
    assert ti.icons == 'heart'
    print("✓ test_public_attribute_assignment passed")


if __name__ == '__main__':
    tests = [
        test_parse_hex_color_6digit,
        test_parse_hex_color_3digit,
        test_parse_named_colors,
        test_parse_invalid_color,
        test_parse_border_solid,
        test_parse_border_dashed,
        test_parse_border_dotted,
        test_parse_border_invalid,
        test_icons_property_setter_string,
        test_icons_property_setter_list,
        test_icons_property_clears_cache,
        test_public_attribute_assignment,
    ]
    
    passed = 0
    failed = 0
    
    print("Running icon rendering tests...\n")
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Tests passed: {passed}")
    print(f"Tests failed: {failed}")
    print(f"Total: {passed + failed}")
    
    sys.exit(0 if failed == 0 else 1)
