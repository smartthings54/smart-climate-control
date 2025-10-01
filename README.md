# Smart Climate Control for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub Release](https://img.shields.io/github/release/smartthings54/smart-climate-control.svg)](https://github.com/smartthings54/smart-climate-control/releases)
[![License](https://img.shields.io/github/license/smartthings54/smart-climate-control.svg)](LICENSE)

This project started out as a Node-RED flow but has been rebuilt as a native Home Assistant integration.
The goal is to make climate management simpler and more flexible instead of editing flows, 
configuration can now be adjusted directly from the Home Assistant control panel.

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

 - **Heat Pump Contact Sensor**: Binary sensor to verify heat pump is actually running (recommended for IR/SmartIR controlled devices)
  
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
- **Bed Sensor**: Binary sensor or input_boolean for sleep detection

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
- **`climate.YOUR_CLIMATE_ENTITY`** - Main climate control with OFF/HEAT/AUTO modes

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
  - entity: climate.YOUR_CLIMATE_ENTITY
  - entity: sensor.smart_climate_status
  - entity: sensor.smart_climate_mode
  - entity: sensor.smart_climate_target
```

### Control Card
```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.YOUR_CLIMATE_ENTITY
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

### DeBug / OverView
```yaml
type: markdown
content: >
  ### Smart Climate Overview  

  {% set target =
  state_attr('sensor.smart_climate_status','heat_pump_temperature')|float(20) %}
  {% set room =
  state_attr('sensor.smart_climate_status','heat_pump_current_temp')|float(20)
  %} {% set deadband_below =
  state_attr('sensor.smart_climate_status','deadband_below')|float(0.5) %} {%
  set deadband_above =
  state_attr('sensor.smart_climate_status','deadband_above')|float(1.0) %} {%
  set mode = state_attr('sensor.smart_climate_status','heat_pump_mode') %} {%
  set action = state_attr('sensor.smart_climate_status','heat_pump_action') %}
  {% set enabled =
  state_attr('sensor.smart_climate_status','smart_control_enabled') %} {% set
  comp_factor =
  state_attr('sensor.smart_climate_status','weather_comp_factor')|float(0.5) %}
  {% set min_comp_temp =
  state_attr('sensor.smart_climate_status','min_comp_temp')|float(16) %} {% set
  max_comp_temp =
  state_attr('sensor.smart_climate_status','max_comp_temp')|float(25) %} {% set
  max_house_temp =
  state_attr('sensor.smart_climate_status','max_house_temp')|float(25) %} {% set
  outside = states('sensor.average_outside_temperature')|float(10) %} {% set
  comp_adjust = (outside|abs * comp_factor) if outside < 0 else 0 %} {% set
  adjusted_target = (target + comp_adjust)|round(1) %}

  Smart Climate Control is {% if enabled %}🟢 enabled{% else %}🔴 disabled{%
  endif %} and set to {{ mode }}. with a room temperature is **{{ room }}°C**
  with a target of **{{ target }}°C**, with a deadband of **{{ deadband_below
  }}°C** below and **{{ deadband_above }}°C** above target, Resulting in **ON**
  at **{{ (target - deadband_below)|round(1) }}°C** and **OFF** at **{{ (target
  + deadband_above)|round(1) }}°C**  

  {% if comp_adjust > 0 %} Because outside is **{{ outside }}°C**, compensation
  adds **+{{ comp_adjust|round(1) }}°C**.   ✅ Adjusted target is now **{{
  adjusted_target }}°C**.   {% else %} No weather compensation applied outside
  is **{{ outside }}°C**{% endif %}


  **Settings:**   

  - Comfort: {{ states('number.smart_climate_comfort_temperature') }}°C   

  - Eco: {{ states('number.smart_climate_eco_temperature') }}°C   

  - Boost: {{ states('number.smart_climate_boost_temperature') }}°C   

  - Max House Temp: {{ max_house_temp }}°C   

  - Comp Range: {{ min_comp_temp }}°C → {{ max_comp_temp }}°C


  **Switches:**   

  - Climate Management: {{ states('switch.smart_climate_climate_management')
  }}   

  - Force Eco Mode: {{ states('switch.smart_climate_force_eco_mode') }}   

  - Force Comfort Mode: {{ states('switch.smart_climate_force_comfort_mode')
  }}  


  **Conditions:**   

  - Outside Temp: {{ outside }}°C   

  - Schedule State: {{ states('schedule.heating') }}   

  - Presence: {{ states('sensor.combined_tracker') }}  

  {% if room <= (target - deadband_below) %} 

  🔥 **System should be HEATING** (room is {{ (target - room)|round(1) }}°C
  below target)   {% elif room >= (target + deadband_above) %} ❄️ **System
  should be OFF** (room is {{ (room - target)|round(1) }}°C above target)   {%
  else %} 

  ⚖️ **System is in DEADBAND zone** (holding state)   {% endif %}

```

![Smart Climate Overview Card](docs/images/smart-climate-overview.png)

**📊 Install Setting**

If you wish to adjust the setting used at install
   - Min & Max Temperatures
   - Deadband Highs & Lower
   - Weather Compensation Factor
   - Schedule Used

clicking on the gear will revelle all needed 

![Smart Climate Overview Card](docs/images/deadbands.jpg)


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







