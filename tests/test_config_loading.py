import importlib.resources as resources


def test_hassclient_config_loads():
    # Load packaged config via package resource and use HassClient.Config to parse
    cfg_path = resources.files('homeassistant_streamdeck').joinpath('config.yaml')
    from homeassistant_streamdeck.HassClient import Config

    config = Config(str(cfg_path))

    # Basic sanity checks on a few well-known config values from the packaged config
    assert config.get('home_assistant/host') is not None
    assert config.get('streamdeck/brightness') is not None
