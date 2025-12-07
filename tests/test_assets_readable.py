import importlib.resources as resources


def test_read_font_bytes():
    fonts_dir = resources.files('homeassistant_streamdeck').joinpath('Assets').joinpath('Fonts')
    # pick a known font
    font_file = fonts_dir.joinpath('Roboto-Bold.ttf')
    assert font_file.exists(), 'Roboto-Bold.ttf should exist in package assets'
    data = font_file.read_bytes()
    assert len(data) > 1000


def test_read_image_bytes():
    images_dir = resources.files('homeassistant_streamdeck').joinpath('Assets').joinpath('Images')
    img = images_dir.joinpath('light_on.png')
    assert img.exists(), 'light_on.png should exist in package assets'
    data = img.read_bytes()
    assert len(data) > 100
