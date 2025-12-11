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

    def _draw_overlay(self, image, pos, max_size):
        if self._overlay is None:
            return

        max_size = min(image.size, max_size)
        if max_size[0] < 0 or max_size[1] < 0:
            return

        if self._overlay_image is None:
            overlay_path = self._resolve_asset_path(self._overlay)
            self._overlay_image = Image.open(overlay_path).convert("RGBA")

        overlay_image = self._overlay_image.copy()
        overlay_image.thumbnail(max_size, Image.LANCZOS)

        overlay_w, overlay_h = overlay_image.size
        overlay_x = pos[0] + int((max_size[0] - overlay_w) / 2)
        overlay_y = pos[1] + int((max_size[1] - overlay_h) / 2)

        image.paste(overlay_image, (overlay_x, overlay_y), overlay_image)

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
