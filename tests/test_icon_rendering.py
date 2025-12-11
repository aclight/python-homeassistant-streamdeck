"""Tests for icon rendering functionality added in this session."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from PIL import Image
import io

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


class TestColorParsing:
    """Test color parsing functionality."""
    
    def test_parse_hex_color_6digit(self):
        """Test parsing 6-digit hex color."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        color = ti._parse_color('#FF0000')
        assert color == (255, 0, 0)
        
        color = ti._parse_color('#00FF00')
        assert color == (0, 255, 0)
        
        color = ti._parse_color('#0000FF')
        assert color == (0, 0, 255)
    
    def test_parse_hex_color_3digit(self):
        """Test parsing 3-digit hex color shorthand."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        color = ti._parse_color('#F00')
        assert color == (255, 0, 0)
        
        color = ti._parse_color('#0F0')
        assert color == (0, 255, 0)
    
    def test_parse_named_colors(self):
        """Test parsing named colors."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        assert ti._parse_color('red') == (255, 0, 0)
        assert ti._parse_color('green') == (0, 128, 0)
        assert ti._parse_color('blue') == (0, 0, 255)
        assert ti._parse_color('white') == (255, 255, 255)
        assert ti._parse_color('black') == (0, 0, 0)
        assert ti._parse_color('yellow') == (255, 255, 0)
    
    def test_parse_invalid_color(self):
        """Test that invalid colors return None."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        assert ti._parse_color('invalidcolor') is None
        assert ti._parse_color('#GGGGGG') is None


class TestBorderParsing:
    """Test border specification parsing."""
    
    def test_parse_border_solid(self):
        """Test parsing solid border."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        thickness, style, color = ti._parse_border('5px solid red')
        assert thickness == 5
        assert style == 'solid'
        assert color == (255, 0, 0)
    
    def test_parse_border_dashed(self):
        """Test parsing dashed border."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        thickness, style, color = ti._parse_border('2px dashed #FF0000')
        assert thickness == 2
        assert style == 'dashed'
        assert color == (255, 0, 0)
    
    def test_parse_border_dotted(self):
        """Test parsing dotted border."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        thickness, style, color = ti._parse_border('3px dotted blue')
        assert thickness == 3
        assert style == 'dotted'
        assert color == (0, 0, 255)
    
    def test_parse_border_invalid(self):
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


class TestIconSVGRendering:
    """Test SVG icon rendering."""
    
    @patch('Tile.TileImage.cairosvg')
    def test_render_icon_svg_basic(self, mock_cairosvg):
        """Test basic SVG icon rendering."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        # Mock SVG input
        svg_input = '<svg><path stroke="currentColor" stroke-width="2"/></svg>'
        
        # Mock cairosvg output
        png_data = io.BytesIO()
        # Create a minimal PNG
        img = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
        img.save(png_data, format='PNG')
        png_data.seek(0)
        
        mock_cairosvg.svg2png.side_effect = lambda **kwargs: kwargs['write_to'].write(png_data.getvalue())
        
        result = ti._render_icon_svg(svg_input, 32, (255, 0, 0), 2)
        
        assert result is not None
        assert isinstance(result, Image.Image)
        assert result.mode == 'RGBA'
        assert result.size == (32, 32)
    
    @patch('Tile.TileImage.cairosvg')
    def test_render_icon_svg_color_replacement(self, mock_cairosvg):
        """Test that SVG colors are properly replaced."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        svg_input = '<svg><path stroke="currentColor" stroke-width="2"/></svg>'
        
        # Mock cairosvg
        png_data = io.BytesIO()
        img = Image.new('RGBA', (32, 32))
        img.save(png_data, format='PNG')
        png_data.seek(0)
        
        def capture_svg(**kwargs):
            # Store the modified SVG for inspection
            capture_svg.last_svg = kwargs['bytestring'].decode()
            kwargs['write_to'].write(png_data.getvalue())
        
        mock_cairosvg.svg2png.side_effect = capture_svg
        
        ti._render_icon_svg(svg_input, 32, (255, 128, 0), 3)
        
        # Check that color and stroke were replaced
        assert 'stroke="rgb(255, 128, 0)"' in capture_svg.last_svg
        assert 'stroke-width="3"' in capture_svg.last_svg
    
    @patch('Tile.TileImage.cairosvg')
    def test_render_icon_svg_whitespace_cleanup(self, mock_cairosvg):
        """Test that SVG whitespace is properly cleaned."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        # SVG with newlines and extra whitespace (like tabler_icons produces)
        svg_input = """<svg>
  <path stroke="currentColor" 
        stroke-width="2"
  />
</svg>"""
        
        png_data = io.BytesIO()
        img = Image.new('RGBA', (32, 32))
        img.save(png_data, format='PNG')
        png_data.seek(0)
        
        def capture_svg(**kwargs):
            capture_svg.last_svg = kwargs['bytestring'].decode()
            kwargs['write_to'].write(png_data.getvalue())
        
        mock_cairosvg.svg2png.side_effect = capture_svg
        
        ti._render_icon_svg(svg_input, 32, (0, 0, 0), 2)
        
        # Whitespace should be cleaned (no newlines in the middle)
        assert '\n' not in capture_svg.last_svg or capture_svg.last_svg.count('\n') == 0


class TestIconProperties:
    """Test icon property management."""
    
    def test_icons_property_setter_string(self):
        """Test setting icons as string."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        ti.icons = 'heart'
        assert ti.icons == 'heart'
    
    def test_icons_property_setter_list(self):
        """Test setting icons as list."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        icon_list = ['heart', 'star']
        ti.icons = icon_list
        assert ti.icons == icon_list
    
    def test_icons_property_clears_cache(self):
        """Test that setting icons clears the pixel cache."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        # Simulate cached pixels
        ti._pixels = 'some_cached_data'
        
        # Setting icons should clear cache
        ti.icons = 'heart'
        assert ti._pixels is None


class TestIconDrawing:
    """Test icon drawing on tiles."""
    
    @patch('Tile.TileImage.tabler_icons')
    @patch('Tile.TileImage.cairosvg')
    def test_draw_single_icon_parsing(self, mock_cairosvg, mock_tabler):
        """Test that icon specifications are parsed correctly."""
        deck = DummyDeck()
        deck.key_count = 1
        ti = TileImage(deck)
        
        # Create a mock image
        image = Image.new('RGB', (72, 72), color='white')
        
        # Mock tabler_icons
        svg_content = '<svg><path stroke="currentColor" stroke-width="2"/></svg>'
        mock_tabler.get_icon.return_value = svg_content
        
        # Mock cairosvg to return a rendered icon
        png_data = io.BytesIO()
        icon_img = Image.new('RGBA', (32, 32), (255, 0, 0, 255))
        icon_img.save(png_data, format='PNG')
        png_data.seek(0)
        
        mock_cairosvg.svg2png.side_effect = lambda **kwargs: kwargs['write_to'].write(png_data.getvalue())
        
        # Draw icon with parameters
        ti._draw_single_icon(image, 'heart size=32 color=red x=20 y=20 stroke=2')
        
        # Verify tabler_icons was called
        mock_tabler.get_icon.assert_called_once_with('heart')
    
    @patch('Tile.TileImage.tabler_icons')
    def test_draw_icons_missing_tabler_icons(self, mock_tabler):
        """Test handling when tabler_icons is not installed."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        image = Image.new('RGB', (72, 72))
        
        # Simulate ImportError
        mock_tabler.side_effect = ImportError()
        
        # Should handle gracefully
        with patch('Tile.TileImage.logging') as mock_logging:
            ti._draw_single_icon(image, 'heart')
            mock_logging.warning.assert_called()


class TestOverlayFileHandling:
    """Test overlay file handling improvements."""
    
    def test_overlay_nonexistent_file_skipped(self):
        """Test that nonexistent overlay files are skipped without error."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        image = Image.new('RGB', (72, 72))
        
        # Set overlay to nonexistent path
        ti.overlay = '/nonexistent/path/overlay.png'
        
        # Should not raise exception
        try:
            ti._draw_overlay(image, (0, 0), (72, 72))
        except FileNotFoundError:
            pytest.fail("Should not raise FileNotFoundError for missing overlay")
    
    def test_overlay_directory_skipped(self):
        """Test that directory paths are skipped for overlay."""
        deck = DummyDeck()
        ti = TileImage(deck)
        
        image = Image.new('RGB', (72, 72))
        
        # Set overlay to a directory
        ti.overlay = '/tmp'
        
        # Should not raise exception
        try:
            ti._draw_overlay(image, (0, 0), (72, 72))
        except (IsADirectoryError, PermissionError):
            pytest.fail("Should handle directory path gracefully")


class TestPublicAttributeInterface:
    """Test that public attributes work correctly."""
    
    def test_public_attribute_assignment(self):
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
