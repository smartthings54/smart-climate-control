# Smart Climate Control for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/smartthings54/smart-climate-control.svg)](https://github.com/smartthings54/smart-climate-control/releases)
[![License](https://img.shields.io/github/license/smartthings54/smart-climate-control.svg)](LICENSE)

This project started out as a Node-RED flow but has been rebuilt as a native Home Assistant integration.
The goal is to make climate management simpler and more flexible — instead of editing flows, configuration can now be adjusted directly from the Home Assistant control panel.

The majority of the code was generated with the help of AI, with my role focused on integration, testing, and making it work within my setup.

## 🌟 Features

- **🌡️ Intelligent Temperature Control**
  - Deadband control to prevent cycling
  - Weather compensation for cold days (when outside sensor configured)
  - Multiple temperature presets (Comfort, Eco, Boost)
  - Adjustable temperature settings via number entities
  
- **🏠 Smart Home Integration**
  - Occupancy-based heating via presence tracker
  - Sleep detection for automatic eco mode (requires 2 bed sensors)
  - Door/window monitoring to prevent energy waste
  - Schedule integration with mode support (comfort/eco/boost/off)
  
- **⚡ Energy Optimization**
  - House average temperature limits
  - Configurable deadband ranges above/below target
  - Maximum/minimum compensation temperature limits
  
- **📊 Comprehensive Monitoring**
  - Real-time status display via sensors
  - Debug information showing current logic
  - Climate entity with proper HVAC modes
  - Multiple switch controls for force modes

## 📋 Prerequisites

- Home Assistant 2024.1.0 or newer
- HACS (Home Assistant Community Store) installed
- The following entities in your Home Assistant:
  - A climate entity (heat pump/thermostat) to control
  - Room temperature sensor
  - Outside temperature sensor (optional but recommended for weather compensation)

## 🚀 Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Click on "Integrations"
3. Click the three dots menu in the top right
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/smartthings54/smart-climate-control`
6. Select "Integration" as the category
7. Click "Add"
8. Search for "Smart Climate Control"
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from GitHub
2. Extract the `smart_climate_control` folder
3. Copy it to your `custom_components` directory:
   ```
   config/custom_components/smart_climate_control/
   ```
4. Restart Home Assistant

## ⚙️ Configuration

### Initial Setup

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **Smart Climate Control**
4. Follow the setup wizard:
   - Select your heat pump/climate entity to control
   - Choose temperature sensors
   - Configure optional features

### Configuration Options

#### Required Entities
- **Heat Pump Entity**: Your climate device to control
- **Room Temperature Sensor**: The room you want to control

#### Optional Entities
- **Outside Temperature Sensor**: For weather compensation
- **Average House Temperature**: For whole-house temperature monitoring
- **Door Sensor**: Disable heating when door is open for >70 seconds
- **Presence Tracker**: For occupancy-based control (person/device_tracker/group/sensor/input_boolean)
- **Heating Schedule**: Schedule entity for automatic mode changes
- **Bed Sensors**: Two binary sensors or input_booleans for sleep detection

#### Temperature Settings (Configurable via Integration Options)
- **Comfort Temperature**: Default 20°C (16-25°C range)
- **Eco Temperature**: Default 18°C (16-25°C range)  
- **Boost Temperature**: Default 23°C (16-25°C range)

#### Advanced Settings (Configurable via Integration Options)
- **Deadband Below**: 0.5°C (0.1-2°C range) - turn ON when temp drops this much below target
- **Deadband Above**: 0.5°C (0.1-2°C range) - turn OFF when temp rises this much above target
- **Max House Temperature**: 25°C (20-30°C range) - safety shutoff limit
- **Weather Compensation Factor**: 0.5 (0-1 range) - how much to boost temp based on outside temp
- **Max Compensated Temperature**: 25°C (20-30°C range)
- **Min Compensated Temperature**: 16°C (14-20°C range)

## 🎛️ Created Entities

### Climate Entity
- **`climate.smart_climate_control`** - Main climate control with OFF/HEAT/AUTO modes

### Switches  
- **`switch.smart_climate_climate_management`** - Master enable/disable for smart control
- **`switch.smart_climate_force_comfort_mode`** - Force comfort temperature 
- **`switch.smart_climate_force_eco_mode`** - Force eco temperature

### Sensors
- **`sensor.smart_climate_status`** - Current system status and debug info
- **`sensor.smart_climate_mode`** - Current active mode (Comfort/Eco/Force Comfort/etc)
- **`sensor.smart_climate_target`** - Target temperature being used

### Number Entities (for adjusting temperatures)
- **`number.smart_climate_boost_temperature`** - Adjust boost temperature
- **`number.smart_climate_comfort_temperature`** - Adjust comfort temperature  
- **`number.smart_climate_eco_temperature`** - Adjust eco temperature

## 📱 Dashboard Cards

### Basic Status Card
```yaml
type: entities
entities:
  - entity: climate.smart_climate_control
  - entity: sensor.smart_climate_status
  - entity: sensor.smart_climate_mode
  - entity: sensor.smart_climate_target
```

### Control Card
```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.smart_climate_control
  - type: entities
    entities:
      - entity: switch.smart_climate_climate_management
      - entity: switch.smart_climate_force_comfort_mode
      - entity: switch.smart_climate_force_eco_mode
```

### Temperature Settings Card
```yaml
type: entities
entities:
  - entity: number.smart_climate_boost_temperature
  - entity: number.smart_climate_comfort_temperature
  - entity: number.smart_climate_eco_temperature
```

### Debug/Overview Card
```yaml
type: markdown
content: >
  ### Smart Climate Overview  

  {% set target = state_attr('sensor.smart_climate_status','heat_pump_temperature')|float(20) %}
  {% set room = state_attr('sensor.smart_climate_status','heat_pump_current_temp')|float(20) %}
  {% set deadband_below = state_attr('sensor.smart_climate_status','deadband_below')|float(0.5) %}
  {% set deadband_above = state_attr('sensor.smart_climate_status','deadband_above')|float(1.0) %}
  {% set mode = state_attr('sensor.smart_climate_status','heat_pump_mode') %}
  {% set action = state_attr('sensor.smart_climate_status','heat_pump_action') %}
  {% set enabled = state_attr('sensor.smart_climate_status','smart_control_enabled') %}
  
  Smart Climate Control is {% if enabled %}🟢 enabled{% else %}🔴 disabled{% endif %} 
  and set to {{ mode }}. Room temperature is **{{ room }}°C** with a target of **{{ target }}°C**.
  
  **Deadband:** ON at **{{ (target - deadband_below)|round(1) }}°C** / OFF at **{{ (target + deadband_above)|round(1) }}°C**
  
  **Temperature Settings:**   
  - Comfort: {{ states('number.smart_climate_comfort_temperature') }}°C   
  - Eco: {{ states('number.smart_climate_eco_temperature') }}°C   
  - Boost: {{ states('number.smart_climate_boost_temperature') }}°C   

  **Control Switches:**   
  - Climate Management: {{ states('switch.smart_climate_climate_management') }}   
  - Force Eco Mode: {{ states('switch.smart_climate_force_eco_mode') }}   
  - Force Comfort Mode: {{ states('switch.smart_climate_force_comfort_mode') }}  
```

## 🔧 Services

### smart_climate_control.force_eco
Force the system into eco mode.

```yaml
service: smart_climate_control.force_eco
data:
  enable: true  # or false to disable
```

### smart_climate_control.force_comfort
Force the system into comfort mode.

```yaml
service: smart_climate_control.force_comfort
data:
  enable: true  # or false to disable
```

### smart_climate_control.reset_temperatures
Reset all temperature settings to defaults.

```yaml
service: smart_climate_control.reset_temperatures
```

## 🤖 Automations

### Example: Schedule-Based Mode Changes
```yaml
automation:
  - alias: "Morning Comfort Mode"
    trigger:
      - platform: time
        at: "06:00:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.smart_climate_force_eco_mode

  - alias: "Night Eco Mode"  
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: switch.turn_on
        target:
          entity_id: switch.smart_climate_force_eco_mode
```

### Example: Away Mode
```yaml
automation:
  - alias: "Away Mode"
    trigger:
      - platform: state
        entity_id: person.YOUR_ENTITY
        to: "not_home"
        for: "00:10:00"
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.smart_climate_climate_management
```

## 🎯 How It Works

The system operates on a 60-second cycle:

1. **Data Collection**: Gathers all sensor readings
2. **Decision Logic**: Evaluates conditions in priority order:
   - System enabled?
   - Force modes active? (Force Comfort > Force Eco)
   - Anyone home? (if presence tracker configured)
   - Door open too long? (>70 seconds)
   - House too hot? (average temperature limit)
   - Room temperature vs target with deadband
3. **Weather Compensation**: Adjusts target up for cold outside temps (if outside sensor configured)
4. **Action Execution**: Controls heat pump accordingly

### Temperature Control Logic

- **Heating ON**: When room temp ≤ (target - deadband_below)
- **Heating OFF**: When room temp ≥ (target + deadband_above)  
- **Maintain State**: When in deadband zone

### HVAC Mode Behavior

- **OFF**: Smart control disabled, heat pump turned off
- **AUTO**: Smart control enabled, follows schedule/logic
- **HEAT**: Smart control enabled + force comfort mode active

### Safety Features

- Maximum house temperature limit 
- Temperature range limits (16-25°C for user settings)
- Automatic shutoff when doors open >70 seconds
- Sensor failure fallbacks (outside temp defaults to 5°C)

## 🐛 Troubleshooting

### System Not Heating
1. Check if **Climate Management** switch is ON
2. Verify someone is home (if using presence tracker)
3. Check door sensors aren't triggered  
4. Review the **Status** sensor for details
5. Check if **Force Eco Mode** is accidentally enabled

### Temperature Not Changing
1. Check if **Force modes** are overriding schedule
2. Verify you're in the deadband zone (check Status sensor)
3. Check temperature settings via Number entities
4. Review schedule entity state (if configured)

### Controls Not Working
1. Make sure you're using the climate entity or switches, not calling services on the controlled heat pump directly
2. Check Home Assistant logs for "Climate:" debug messages
3. Verify the integration is properly controlling the heat pump entity

## 📝 Support

- **Issues**: [GitHub Issues](https://github.com/smartthings54/smart-climate-control/issues)
- **Discussions**: [GitHub Discussions](https://github.com/smartthings54/smart-climate-control/discussions)
- **Updates**: Watch the repository for updates

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔄 Changelog

### Version 1.0.0
- Initial release
- Core climate control functionality
- Weather compensation
- Sleep detection  
- Door monitoring
- HACS compatibility
- Configurable deadband and temperature settings
- Force mode switches
- Schedule entity support with options configuration
