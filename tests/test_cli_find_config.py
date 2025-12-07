import os
import tempfile
import importlib


def test_cli_find_packaged_config(tmp_path):
    # Import the cli module; it delegates to packaged HassClient
    cli = importlib.import_module('homeassistant_streamdeck.cli')

    # Ensure no config.yaml in cwd for this test by using a temp dir
    old_cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        config_path = cli._find_config_path(None)
        assert os.path.exists(config_path), 'Expected fallback packaged config to be written to a temp file'

        # basic sanity: file should contain the home_assistant section header
        with open(config_path, 'r', encoding='utf-8') as fh:
            contents = fh.read()
        assert 'home_assistant' in contents

    finally:
        # cleanup temp file if created
        try:
            if config_path and config_path.startswith(tempfile.gettempdir()):
                os.unlink(config_path)
        except Exception:
            pass
        os.chdir(old_cwd)
