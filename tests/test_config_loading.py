import importlib.resources as resources
import os


def test_hassclient_config_loads():
    # Load example config and use HassClient.Config to parse
    # The example config is in the repo root, not the package
    example_config = os.path.join(os.path.dirname(__file__), '..', 'config.example.yaml')
    from homeassistant_streamdeck.HassClient import Config

    config = Config(example_config)

    # Basic sanity checks on a few well-known config values from the example config
    assert config.get('home_assistant/host') is not None
    assert config.get('streamdeck/brightness') is not None
