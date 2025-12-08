import importlib.resources as resources
from pathlib import Path


def test_package_root_importable():
    # ensure package is importable without importing heavy dependencies
    package_root = resources.files('homeassistant_streamdeck')
    assert package_root is not None


def test_assets_present():
    package_root = resources.files('homeassistant_streamdeck')
    assets = package_root.joinpath('Assets')
    assert assets.exists(), 'Assets directory should exist in package'

    fonts = assets.joinpath('Fonts')
    images = assets.joinpath('Images')

    assert fonts.exists(), 'Assets/Fonts should exist'
    assert images.exists(), 'Assets/Images should exist'

    # Ensure at least one font and one image file exist
    font_files = [p for p in fonts.iterdir() if p.is_file() and p.suffix.lower() in ('.ttf', '.otf')]
    image_files = [p for p in images.iterdir() if p.is_file() and p.suffix.lower() in ('.png', '.jpg', '.jpeg')]

    assert len(font_files) >= 1, 'No font files found in Assets/Fonts'
    assert len(image_files) >= 1, 'No image files found in Assets/Images'
