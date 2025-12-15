# StreamDeck Brightness Control Setup Guide

The StreamDeck brightness can now be controlled dynamically from Home Assistant using any numeric entity (0-100).

## Configuration

In your `config.yaml`, add the `brightness_entity` option:

```yaml
streamdeck:
  brightness: 20  # Default brightness when not controlled by entity
  brightness_entity: input_number.streamdeck_brightness
```

## Home Assistant Setup Options

Choose one of the following methods to create a brightness control entity in Home Assistant:

### Option 1: Input Number Helper (Recommended)

This is the easiest option - create a manual number input in Home Assistant.

**Via Home Assistant UI:**
1. Go to Settings → Devices & Services → Helpers
2. Click "Create Helper" → "Number"
3. Configure:
   - **Name:** StreamDeck Brightness
   - **Unit of measurement:** % (optional)
   - **Min value:** 0
   - **Max value:** 100
   - **Step:** 1
   - **Initial value:** 20
4. Click Create

The entity ID will be `input_number.streamdeck_brightness`

**Via YAML:**
Add to your `configuration.yaml`:

```yaml
input_number:
  streamdeck_brightness:
    name: StreamDeck Brightness
    min: 0
    max: 100
    step: 1
    unit_of_measurement: "%"
    initial: 20
```

Then restart Home Assistant.

---

### Option 2: Template Sensor (Based on Light Brightness)

Control StreamDeck brightness based on another light's brightness:

```yaml
template:
  - sensor:
      - name: StreamDeck Brightness
        unique_id: streamdeck_brightness
        unit_of_measurement: "%"
        state: "{{ (state_attr('light.living_room', 'brightness') or 20) | int(0) / 2.55 | int }}"
```

Then set in `config.yaml`:
```yaml
streamdeck:
  brightness_entity: sensor.streamdeck_brightness
```

---

### Option 3: Template Sensor (Based on Time of Day)

Auto-adjust brightness based on time of day:

```yaml
template:
  - sensor:
      - name: StreamDeck Brightness
        unique_id: streamdeck_brightness
        unit_of_measurement: "%"
        state: >
          {% set hour = now().hour %}
          {% if 6 <= hour < 12 %}
            30
          {% elif 12 <= hour < 18 %}
            50
          {% elif 18 <= hour < 21 %}
            20
          {% else %}
            5
          {% endif %}
```

Then set in `config.yaml`:
```yaml
streamdeck:
  brightness_entity: sensor.streamdeck_brightness
```

---

### Option 4: Sensor from Integration

If you have a light sensor or other brightness sensor, you can use it directly:

```yaml
streamdeck:
  brightness_entity: sensor.ambient_light_brightness
```

Just ensure the sensor's state is a numeric value between 0-100.

---

## Behavior

- **When `brightness_entity` is NOT configured:** The StreamDeck uses the default `brightness` value (20%)
- **When `brightness_entity` IS configured:** 
  - The StreamDeck brightness is set to the entity's value when the screen turns on
  - The brightness updates whenever the entity value changes
  - Brightness only applies when the screen is ON (not during screensaver)
  - Values outside 0-100 are automatically clamped to the valid range

## Automation Examples

### Example 1: Adjust brightness with a script

```yaml
script:
  increase_streamdeck_brightness:
    sequence:
      - service: input_number.set_value
        target:
          entity_id: input_number.streamdeck_brightness
        data:
          value: "{{ (states('input_number.streamdeck_brightness') | float(0) + 10) | min(100) }}"
```

### Example 2: Sync with room lights

```yaml
automation:
  - alias: Sync StreamDeck brightness with living room
    trigger:
      - platform: state
        entity_id: light.living_room
        attribute: brightness
    action:
      - service: input_number.set_value
        target:
          entity_id: input_number.streamdeck_brightness
        data:
          # Convert light brightness (0-255) to StreamDeck percentage (0-100)
          value: "{{ ((state_attr('light.living_room', 'brightness') or 0) / 2.55) | int }}"
```

### Example 3: Dim at night automatically

```yaml
automation:
  - alias: StreamDeck brightness at night
    trigger:
      - platform: time
        at: "21:00:00"
    action:
      - service: input_number.set_value
        target:
          entity_id: input_number.streamdeck_brightness
        data:
          value: 10
  
  - alias: StreamDeck brightness in morning
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: input_number.set_value
        target:
          entity_id: input_number.streamdeck_brightness
        data:
          value: 30
```

## Troubleshooting

- **Brightness not updating:** Check the entity ID in your config matches exactly (case-sensitive)
- **Invalid brightness value:** Ensure the entity's state is numeric (0-100 range works best)
- **Text values in entity:** If the entity contains text, it will be logged as a warning and ignored
- **Check logs:** Look for "BrightnessController" messages in your logs for debugging
