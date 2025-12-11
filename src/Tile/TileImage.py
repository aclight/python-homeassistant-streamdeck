#   Python StreamDeck HomeAssistant Client
#      Released under the MIT license
#
#   dean [at] fourwalledcubicle [dot] com
#         www.fourwalledcubicle.com
#

from PIL import Image, ImageDraw, ImageFont
from StreamDeck.ImageHelpers import PILHelper
import os
import importlib.resources as pkg_resources
from pathlib import Path
import logging
import cairosvg
import tabler_icons
import io


class TileImage(object):
    def __init__(self, deck, base_path=None):
        self._pixels = None
        self._overlay_image = None
        self._deck = deck
        self._base_path = base_path

        self.color = (0, 0, 0)
        self.overlay = None
        self.label = None
        self.label_font = None
        self.label_size = None
        self.value = None
        self.value_font = None
        self.value_size = None
        self.border = None
        self.icons = None

    @property
    def color(self):
        return self._color

    @property
    def overlay(self):
        return self._overlay

    @property
    def label(self):
        return self._label

    @property
    def label_font(self):
        return self._label_font

    @property
    def label_size(self):
        return self._label_size
    
    @property
    def value(self):
        return self._value

    @property
    def value_font(self):
        return self._value_font
        
    @property
    def value_size(self):
        return self._value_size

    @color.setter
    def color(self, value):
        self._color = value
        self._pixels = None

    @overlay.setter
    def overlay(self, overlay):
        self._overlay = overlay
        self._overlay_image = None
        self._pixels = None

    @label.setter
    def label(self, text):
        self._label = text
        self._pixels = None

    @label_font.setter
    def label_font(self, font):
        self._label_font = font
        self._pixels = None

    @label_size.setter
    def label_size(self, size):
        self._label_size = size
        self._pixels = None

    @value.setter
    def value(self, value):
        self._value = value
        self._pixels = None

    @value_font.setter
    def value_font(self, font):
        self._value_font = font
        self._pixels = None

    @value_size.setter
    def value_size(self, size):
        self._value_size = size
        self._pixels = None

    @property
    def border(self):
        return self._border

    @border.setter
    def border(self, border):
        self._border = border
        self._pixels = None

    @property
    def icons(self):
        return self._icons

    @icons.setter
    def icons(self, icons):
        self._icons = icons
        self._pixels = None

    def _draw_overlay(self, image, pos, max_size):
        if self._overlay is None or self._overlay == '':
            return

        max_size = min(image.size, max_size)
        if max_size[0] < 0 or max_size[1] < 0:
            return

        if self._overlay_image is None:
            overlay_path = self._resolve_asset_path(self._overlay)
            # Skip if the overlay path is just a directory (happens when path is invalid)
            if os.path.isdir(overlay_path):
                return
            # Skip if the overlay file doesn't exist
            if not os.path.isfile(overlay_path):
                return
            self._overlay_image = Image.open(overlay_path).convert("RGBA")

        overlay_image = self._overlay_image.copy()
        overlay_image.thumbnail(max_size, Image.LANCZOS)

        overlay_w, overlay_h = overlay_image.size
        overlay_x = pos[0] + int((max_size[0] - overlay_w) / 2)
        overlay_y = pos[1] + int((max_size[1] - overlay_h) / 2)

        image.paste(overlay_image, (overlay_x, overlay_y), overlay_image)

    def _draw_icons(self, image):
        """Draw one or more tabler icons on the image.
        
        Icons are drawn on top of the overlay but under border/label/value.
        """
        if self.icons is None or self.icons == '':
            return

        # Normalize icons to a list
        icons_list = []
        if isinstance(self._icons, str):
            # Single icon specification
            icons_list = [self._icons]
        elif isinstance(self._icons, list):
            icons_list = self._icons
        else:
            return

        for icon_spec in icons_list:
            self._draw_single_icon(image, icon_spec)

    def _draw_single_icon(self, image, icon_spec):
        """Draw a single tabler icon.
        
        Icon spec format: "icon_name [size=N] [color=hex|name] [x=N] [y=N] [stroke=N]"
        Example: "heart size=32 color=red x=10 y=10 stroke=2"
        """
        # Parse icon specification
        parts = icon_spec.strip().split()
        if not parts:
            return

        icon_name = parts[0]
        params = {}

        # Parse parameters
        for part in parts[1:]:
            if '=' in part:
                key, value = part.split('=', 1)
                params[key.lower()] = value.lower()

        # Get icon defaults
        size = int(params.get('size', image.width))
        color = self._parse_color(params.get('color', 'white'))
        stroke = int(params.get('stroke', 2))
        x = int(params.get('x', (image.width - size) // 2))
        y = int(params.get('y', (image.height - size) // 2))

        if color is None:
            color = (255, 255, 255)

        try:
            # Get the icon SVG
            icon_svg = tabler_icons.get_icon(icon_name)
            if icon_svg is None:
                logging.warning(f"Icon '{icon_name}' not found in tabler_icons")
                return

            icon_image = self._render_icon_svg(icon_svg, size, color, stroke)
            if icon_image is None:
                return

            # Draw the icon on the image
            image.paste(icon_image, (x, y), icon_image)

        except Exception as e:
            # Log the error instead of silently failing
            logging.error(f"Error drawing icon '{icon_name}': {e}", exc_info=True)

    def _render_icon_svg(self, svg_string, size, color, stroke):
        """Render a tabler icon SVG to a PIL Image using cairosvg."""
        # Convert markupsafe.Markup to string if needed
        svg_str = str(svg_string)
        
        # Clean up the SVG: remove line breaks and extra whitespace
        # The tabler_icons SVG has formatting that breaks XML parsing
        svg_str = ' '.join(svg_str.split())

        # Modify SVG to use the desired color and stroke
        svg_modified = svg_str.replace('stroke="currentColor"', f'stroke="rgb{color}"')
        svg_modified = svg_modified.replace('stroke-width="2"', f'stroke-width="{stroke}"')

        # Render to PNG in memory
        png_data = io.BytesIO()
        cairosvg.svg2png(bytestring=svg_modified.encode(), write_to=png_data, output_width=size, output_height=size)
        png_data.seek(0)

        icon_image = Image.open(png_data).convert("RGBA")
        return icon_image


    def _parse_border(self, border_spec):
        """Parse a CSS-like border specification: 'thickness style color'
        
        Examples:
        - '5px solid red'
        - '2px dashed #FF0000'
        - '3px dotted blue'
        
        Returns:
            tuple: (thickness_px, style, color_tuple) or (None, None, None) if invalid
        """
        if border_spec is None or border_spec == '':
            return (None, None, None)

        parts = border_spec.strip().split()
        if len(parts) < 3:
            return (None, None, None)

        try:
            # Parse thickness (remove 'px' suffix)
            thickness_str = parts[0].rstrip('px')
            thickness = int(thickness_str)

            # Parse style
            style = parts[1].lower()
            if style not in ['solid', 'dashed', 'dotted']:
                return (None, None, None)

            # Parse color
            color_name = parts[2].lower()
            color = self._parse_color(color_name)
            if color is None:
                return (None, None, None)

            return (thickness, style, color)
        except (ValueError, IndexError):
            return (None, None, None)

    def _parse_color(self, color_spec):
        """Parse a color specification.
        
        Supports:
        - Standard color names (red, green, blue, black, white, etc.)
        - Hex RGB values (#FF0000, #0F0, etc.)
        
        Returns:
            tuple: (R, G, B) or None if invalid
        """
        # Hex color
        if color_spec.startswith('#'):
            try:
                hex_str = color_spec.lstrip('#')
                if len(hex_str) == 6:
                    r = int(hex_str[0:2], 16)
                    g = int(hex_str[2:4], 16)
                    b = int(hex_str[4:6], 16)
                    return (r, g, b)
                elif len(hex_str) == 3:
                    # Short form like #F0A
                    r = int(hex_str[0] * 2, 16)
                    g = int(hex_str[1] * 2, 16)
                    b = int(hex_str[2] * 2, 16)
                    return (r, g, b)
            except ValueError:
                pass
        
        # Named colors
        color_map = {
            'red': (255, 0, 0),
            'green': (0, 128, 0),
            'blue': (0, 0, 255),
            'black': (0, 0, 0),
            'white': (255, 255, 255),
            'yellow': (255, 255, 0),
            'cyan': (0, 255, 255),
            'magenta': (255, 0, 255),
            'gray': (128, 128, 128),
            'grey': (128, 128, 128),
            'orange': (255, 165, 0),
            'purple': (128, 0, 128),
            'pink': (255, 192, 203),
            'brown': (165, 42, 42),
        }
        
        return color_map.get(color_spec)

    def _draw_border(self, image):
        """Draw a rounded rectangle border on the image.
        
        The border is drawn on top of existing content but will be covered by labels/values.
        """
        if self._border is None:
            return

        thickness, style, color = self._parse_border(self._border)
        if thickness is None or style is None or color is None:
            return

        d = ImageDraw.Draw(image)
        
        # Define the bounding box with a small fixed margin to keep border inside image
        margin = 1
        bbox = [margin, margin, image.width - margin, image.height - margin + 1]
        
        # Draw based on style
        if style == 'solid':
            d.rounded_rectangle(bbox, radius=10, outline=color, width=thickness)
        elif style == 'dashed':
            self._draw_dashed_rounded_rectangle(d, bbox, color, thickness, radius=10)
        elif style == 'dotted':
            self._draw_dotted_rounded_rectangle(d, bbox, color, thickness, radius=10)

    def _draw_dashed_rounded_rectangle(self, draw, bbox, color, width, radius=10):
        """Draw a dashed rounded rectangle."""
        x0, y0, x1, y1 = bbox
        
        # Draw rounded corners and edges with dashes
        dash_length = 4
        gap_length = 2
        
        # Top edge
        x = x0 + radius
        while x < x1 - radius:
            draw.line([(x, y0), (min(x + dash_length, x1 - radius), y0)], fill=color, width=width)
            x += dash_length + gap_length
        
        # Bottom edge
        x = x0 + radius
        while x < x1 - radius:
            draw.line([(x, y1), (min(x + dash_length, x1 - radius), y1)], fill=color, width=width)
            x += dash_length + gap_length
        
        # Left edge
        y = y0 + radius
        while y < y1 - radius:
            draw.line([(x0, y), (x0, min(y + dash_length, y1 - radius))], fill=color, width=width)
            y += dash_length + gap_length
        
        # Right edge
        y = y0 + radius
        while y < y1 - radius:
            draw.line([(x1, y), (x1, min(y + dash_length, y1 - radius))], fill=color, width=width)
            y += dash_length + gap_length
        
        # Draw corner arcs
        corner_bbox = (x0, y0, x0 + radius * 2, y0 + radius * 2)
        draw.arc(corner_bbox, 180, 270, fill=color, width=width)
        
        corner_bbox = (x1 - radius * 2, y0, x1, y0 + radius * 2)
        draw.arc(corner_bbox, 270, 0, fill=color, width=width)
        
        corner_bbox = (x1 - radius * 2, y1 - radius * 2, x1, y1)
        draw.arc(corner_bbox, 0, 90, fill=color, width=width)
        
        corner_bbox = (x0, y1 - radius * 2, x0 + radius * 2, y1)
        draw.arc(corner_bbox, 90, 180, fill=color, width=width)

    def _draw_dotted_rounded_rectangle(self, draw, bbox, color, width, radius=10):
        """Draw a dotted rounded rectangle."""
        x0, y0, x1, y1 = bbox
        
        # Draw rounded corners and edges with dots
        dot_spacing = 3
        dot_size = 1
        
        # Top edge
        x = x0 + radius
        while x < x1 - radius:
            draw.ellipse([x, y0, x + dot_size, y0 + dot_size], fill=color)
            x += dot_spacing
        
        # Bottom edge
        x = x0 + radius
        while x < x1 - radius:
            draw.ellipse([x, y1, x + dot_size, y1 + dot_size], fill=color)
            x += dot_spacing
        
        # Left edge
        y = y0 + radius
        while y < y1 - radius:
            draw.ellipse([x0, y, x0 + dot_size, y + dot_size], fill=color)
            y += dot_spacing
        
        # Right edge
        y = y0 + radius
        while y < y1 - radius:
            draw.ellipse([x1, y, x1 + dot_size, y + dot_size], fill=color)
            y += dot_spacing
        
        # Draw corner arcs
        corner_bbox = (x0, y0, x0 + radius * 2, y0 + radius * 2)
        draw.arc(corner_bbox, 180, 270, fill=color, width=width)
        
        corner_bbox = (x1 - radius * 2, y0, x1, y0 + radius * 2)
        draw.arc(corner_bbox, 270, 0, fill=color, width=width)
        
        corner_bbox = (x1 - radius * 2, y1 - radius * 2, x1, y1)
        draw.arc(corner_bbox, 0, 90, fill=color, width=width)
        
        corner_bbox = (x0, y1 - radius * 2, x0 + radius * 2, y1)
        draw.arc(corner_bbox, 90, 180, fill=color, width=width)

    def _draw_label(self, image):
        if self._label is None:
            return None, None, None, None

        try:
            label_font_path = (self._label_font or 'Assets/Fonts/Roboto-Bold.ttf')
            resolved_label_font = self._resolve_asset_path(label_font_path)
            font = ImageFont.truetype(resolved_label_font, self._label_size or 12)
            d = ImageDraw.Draw(image)

            # Measure text size using a safe fallback path:
            # 1) textbbox (newer Pillow)
            # 2) textsize (older Pillow)
            # 3) font.getsize (fallback)
            try:
                bbox = d.textbbox((0, 0), self._label, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except AttributeError:
                try:
                    w, h = d.textsize(self._label, font=font)
                except AttributeError:
                    try:
                        w, h = font.getsize(self._label)
                    except Exception:
                        w, h = (image.width, 0)

            padding = 2

            pos = ((image.width - w) / 2, padding)
            d.text(pos, self._label, font=font, fill=(255, 255, 255, 128))
            return (pos[0], pos[1], w, h + padding)
        except OSError:
            return (image.width, 0, image.width, 1)

    def _draw_value(self, image):
        if self._value is None:
            return None, None, None, None

        try:
            value_font_path = (self._value_font or 'Assets/Fonts/Roboto-Light.ttf')
            resolved_value_font = self._resolve_asset_path(value_font_path)
            font = ImageFont.truetype(resolved_value_font, self._value_size or 18)
            d = ImageDraw.Draw(image)

            # Measure text size using a safe fallback path:
            # 1) textbbox (newer Pillow)
            # 2) textsize (older Pillow)
            # 3) font.getsize (fallback)
            try:
                bbox = d.textbbox((0, 0), self._value, font=font)
                w = bbox[2] - bbox[0]
                h = bbox[3] - bbox[1]
            except AttributeError:
                try:
                    w, h = d.textsize(self._value, font=font)
                except AttributeError:
                    try:
                        w, h = font.getsize(self._value)
                    except Exception:
                        w, h = (image.width, 0)

            padding = 2
            pos = ((image.width - w) / 2, image.height - h - padding)
            d.text(pos, self._value, font=font, fill=(255, 255, 255, 128))
            return (pos[0], pos[1], w, h + padding)
        except OSError:
            return (image.width, 0, image.width, 1)

    def __getitem__(self, key):
        if self._pixels is None:
            try:
                image = PILHelper.create_image(self._deck, background=self._color)

                l_x, l_y, l_w, l_h = self._draw_label(image)
                v_x, v_y, v_w, v_h = self._draw_value(image)

                o_x = 0
                o_y = (l_y or 0) + (l_h or 0)
                o_w = image.width
                o_h = (v_y or image.height) - o_y

                overlay_pos = (int(o_x), int(o_y))
                overlay_size = (int(o_w), int(o_h))
                self._draw_overlay(image, overlay_pos, overlay_size)
                
                # Draw icons after overlay but before border
                self._draw_icons(image)
                
                # Draw border after icons but before label/value
                self._draw_border(image)
                
                # Redraw label and value on top of the border
                if self._label is not None:
                    try:
                        label_font_path = (self._label_font or 'Assets/Fonts/Roboto-Bold.ttf')
                        resolved_label_font = self._resolve_asset_path(label_font_path)
                        font = ImageFont.truetype(resolved_label_font, self._label_size or 12)
                        d = ImageDraw.Draw(image)
                        pos = ((image.width - (l_w or 0)) / 2, l_y or 0)
                        d.text(pos, self._label, font=font, fill=(255, 255, 255, 128))
                    except OSError:
                        pass
                
                if self._value is not None:
                    try:
                        value_font_path = (self._value_font or 'Assets/Fonts/Roboto-Light.ttf')
                        resolved_value_font = self._resolve_asset_path(value_font_path)
                        font = ImageFont.truetype(resolved_value_font, self.value_size or 18)
                        d = ImageDraw.Draw(image)
                        pos = ((image.width - (v_w or 0)) / 2, (v_y or image.height) - (v_h or 0))
                        d.text(pos, self.value, font=font, fill=(255, 255, 255, 128))
                    except OSError:
                        pass

                self._pixels = PILHelper.to_native_format(self._deck, image)
            except Exception as e:
                logging.error(f"Error rendering tile: {e}", exc_info=True)
                # Create a blank image as fallback
                image = PILHelper.create_image(self._deck, background=self.color)
                self._pixels = PILHelper.to_native_format(self._deck, image)

        return self._pixels[key]

    def _resolve_asset_path(self, path):
        """Resolve an asset path.

        Resolution order:
        1. If `path` exists as given (absolute or relative to cwd), return it
        2. If base_path is set, try relative to base_path (config directory)
        3. Try to find the file inside the installed `homeassistant_streamdeck` package
        
        This allows users to reference assets relative to their config file location,
        such as "Assets/Images/overlay.png" or custom paths like "thumbnails/000.png".
        """
        if path is None:
            raise FileNotFoundError(path)

        # If the path is already a Path-like that exists, return it
        if os.path.exists(path):
            return path

        # If base_path is set, try resolving relative to the config directory
        # This allows users to reference paths like "Assets/Images/overlay.png"
        # relative to where their config.yaml is located
        if self._base_path is not None:
            candidate = os.path.join(self._base_path, path)
            if os.path.exists(candidate):
                return candidate

        # Try to resolve relative to the package root
        try:
            pkg_root = pkg_resources.files('homeassistant_streamdeck')
            candidate = pkg_root.joinpath(path)
            # importlib.resources.Path-like objects may not support is_file directly
            candidate_path = Path(os.fspath(candidate))
            if candidate_path.exists():
                return str(candidate_path)
        except Exception:
            pass

        # As a last resort, return the original path and let the caller handle the error
        return path
