import os
import importlib
import pytest


def test_cli_find_cwd_config(tmp_path):
    """Test that config.yaml is found in current working directory."""
    cli = importlib.import_module('homeassistant_streamdeck.cli')

    # Create a config.yaml in the temp directory
    config_file = tmp_path / 'config.yaml'
    config_file.write_text('debug: False\nhome_assistant:\n  host: localhost\n')

    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        config_path = cli._find_config_path(None)
        assert config_path == os.path.join(tmp_path, 'config.yaml')
    finally:
        os.chdir(old_cwd)


def test_cli_find_explicit_config(tmp_path):
    """Test that explicit --config path works."""
    cli = importlib.import_module('homeassistant_streamdeck.cli')

    # Create a config file at explicit path
    config_file = tmp_path / 'my_config.yaml'
    config_file.write_text('debug: False\nhome_assistant:\n  host: localhost\n')

    config_path = cli._find_config_path(str(config_file))
    assert config_path == str(config_file)


def test_cli_find_no_config_raises_error(tmp_path):
    """Test that FileNotFoundError is raised when no config is found."""
    cli = importlib.import_module('homeassistant_streamdeck.cli')

    # Use empty temp directory with no config
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        with pytest.raises(FileNotFoundError) as exc_info:
            cli._find_config_path(None)
        assert 'No config.yaml found' in str(exc_info.value)
    finally:
        os.chdir(old_cwd)
