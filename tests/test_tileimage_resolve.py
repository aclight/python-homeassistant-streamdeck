import importlib.resources as resources
from Tile.TileImage import TileImage
from StreamDeck.DeviceManager import DeviceManager


def test_tileimage_resolve_asset_exists():
    # Create a minimal TileImage instance using a dummy deck object from StreamDeck
    # We don't actually talk to hardware; PIL/StreamDeck helpers are used only to
    # provide the expected interface in TileImage.__init__.
    decks = DeviceManager().enumerate()
    # If no physical deck present, TileImage still expects a deck-like object.
    # Use the first deck if present, otherwise create a minimal dummy with required attrs.
    if decks:
        deck = decks[0]
    else:
        class _DummyDeck:
            def __init__(self):
                self.key_count = 15
            def __getattr__(self, name):
                def _missing(*a, **k):
                    return None
                return _missing
        deck = _DummyDeck()

    ti = TileImage(deck)

    # Resolve an asset path that should be packaged
    path = ti._resolve_asset_path('Assets/Fonts/Roboto-Bold.ttf')
    assert path is not None
    assert resources.files('homeassistant_streamdeck').joinpath('Assets').joinpath('Fonts').joinpath('Roboto-Bold.ttf').exists()
