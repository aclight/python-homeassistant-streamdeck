# Python Elgato HomeAssistant Client

![Example Deck](ExampleDeck.jpg)

This is an open source Python 3 application to control a
[Home Assistant](http://home-assistant.io) home automation instance remotely,
via an [Elgato Stream Deck](https://www.elgato.com/en/gaming/stream-deck). This
client is designed to be able to run run cross-platform, so that the StreamDeck
can be connected to both full PCs as well as stand-alone Raspberry Pis.

Unlike the official software client, which can be made to integrate with Home
Assistant via it's "Open Website" command macros, this client supports dynamic
updates of the button images to reflect the current entity states.

## Status:

Working. You can define your own page layout in the configuration YAML file, and
attach HomeAssistant lights and other entities to buttons on the StreamDeck. The
current state of the entity can be shown on the button in both text form, as
as image form (live button state updates are supported). The HomeAssistant
action to trigger when a button is pressed is also configurable.

This is my first asyncio project, and I'm not familiar with the technology, so
everything can be heavily improved. If you know asyncio, please submit patches
to help me out!

Nothing is robust yet, and the configuration format used in the `config.yaml`
file is not yet documented.

## Configuration

The project uses a YAML configuration file (`config.yaml`) to describe the
Home Assistant connection, Stream Deck options, tile templates and screen
layouts. When installed, the CLI will look for `./config.yaml` in the current
working directory by default, or you can pass a custom path with
`--config /path/to/config.yaml`.

Key configuration sections:
- **home_assistant**: host, ssl (true/false), port, `api_password` (legacy) or
	`api_token` (long-lived access token).
- **streamdeck**: `brightness` (0-100) and `screensaver` timeout in seconds.
- **tiles**: list of tile templates. Each tile template defines a `type`, the
	`class` to use (e.g. `HassTile`), `states` (a list of render states with
	attributes such as `label`, `label_font`, `overlay`) and an `action`.
- **screens**: pages of tiles. Each screen has a `name` and a `tiles` list with
	`position`, `type`, `name`, and `entity_id` (or `page` when `type: page`).

Example snippet (from the included `config.yaml`):

```yaml
home_assistant:
	host: 192.168.1.142
	ssl: False
	port: ~
	api_token: <your-long-lived-token>

streamdeck:
	brightness: 80
	screensaver: ~

tiles:
	- type: "light"
		class: 'HassTile'
		states:
			- state: 'on'
				label: '{name}'
				label_font: Assets/Fonts/Roboto-Bold.ttf
				overlay: 'Assets/Images/light_on.png'
		action: 'toggle'

screens:
	- name: "home"
		tiles:
			- position: [0, 0]
				type: "light"
				name: "Study"
				entity_id: "light.study"
```

If you install via `pip`, use `hass-streamdeck --config /path/to/config.yaml`
to point to your configuration file; running the script from the cloned
repository using the `src/config.yaml` will behave the same as before.

## Dependencies:

### Python

Python 3.8 or newer is required. On Debian systems, this can usually be
installed via:
```
sudo apt install python3 python3-pip
```

### Python Libraries

You will need to have the following libraries installed:

StreamDeck, [my own library](https://github.com/abcminiuser/python-elgato-streamdeck)
to interface to StreamDeck devices:
```
pip3 install StreamDeck
```

Pillow, the Python Image Library (PIL) fork, for dynamic tile image creation:
```
pip3 install pillow
```

aiohttp, for Websocket communication with Home Assistant:
```
pip3 install aiohttp
```

PyYAML, for configuration file parsing:
```
pip3 install pyyaml
```

## License:

Released under the MIT license:

```
Permission to use, copy, modify, and distribute this software
and its documentation for any purpose is hereby granted without
fee, provided that the above copyright notice appear in all
copies and that both that the copyright notice and this
permission notice and warranty disclaimer appear in supporting
documentation, and that the name of the author not be used in
advertising or publicity pertaining to distribution of the
software without specific, written prior permission.

The author disclaims all warranties with regard to this
software, including all implied warranties of merchantability
and fitness.  In no event shall the author be liable for any
special, indirect or consequential damages or any damages
whatsoever resulting from loss of use, data or profits, whether
in an action of contract, negligence or other tortious action,
arising out of or in connection with the use or performance of
this software.
```
