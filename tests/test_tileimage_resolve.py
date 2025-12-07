import importlib.resources as resources

from Tile.TileImage import TileImage



def test_tileimage_resolve_asset_exists():
    # Use a pure Python dummy deck object to avoid hardware/native library dependencies
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
