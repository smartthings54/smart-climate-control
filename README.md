# Smart Climate Control v2 beta

> ⚠️ **This is the `v2-beta` branch** — a stripped-down rewrite for testing.  
> For the stable release see the `main` branch.

## What's new in v2

- Rebuilt around Home Assistant's `DataUpdateCoordinator` — cleaner state management, proper error handling, and automatic entity state updates.
- Simplified entity set: sensors, switches, and number sliders only (no extra climate entity wrapper).
- Force modes (Comfort / Eco / Boost) are now mutually exclusive — turning one on automatically clears the others.
- All state (temperatures, force mode, enabled flag) persists across restarts via HA storage.

## What's been removed for now

The following features from v1 have been deliberately left out to keep this beta stable and easy to debug. They will be added back incrementally once the core is solid:

- Cooling mode
- Weather compensation
- Presence / occupancy detection
- Door / window sensor
- Average house temperature limit
- Sleep detection (bed sensors)
- Device linking (entity grouping in the device registry)
- Contact sensor verification / retry logic

---

## Entities created

| Entity | Type | Purpose |
|---|---|---|
| `sensor.{name}_status` | Sensor | Current debug status line |
| `sensor.{name}_mode` | Sensor | Active mode (Comfort / Eco / Boost / Disabled) |
| `sensor.{name}_target` | Sensor | Current target temperature |
| `switch.{name}_climate_management` | Switch | Master enable / disable |
| `switch.{name}_force_comfort` | Switch | Override to comfort temperature |
| `switch.{name}_force_eco` | Switch | Override to eco temperature |
| `switch.{name}_force_boost` | Switch | Override to boost temperature |
| `number.{name}_comfort_temperature` | Number | Comfort setpoint (slider) |
| `number.{name}_eco_temperature` | Number | Eco setpoint (slider) |
| `number.{name}_boost_temperature` | Number | Boost setpoint (slider) |

---

## How it works

The system runs on a 60-second cycle:

1. Reads the room temperature sensor.
2. Reads the schedule entity (if configured) to determine the current mode.
3. If a force switch is active it overrides the schedule mode.
4. Applies **deadband control** to decide whether to heat or hold:
   - Turn **ON** when `room_temp ≤ target − deadband_below`
   - Turn **OFF** when `room_temp ≥ target + deadband_above`
   - **Hold** current state while inside the band (prevents rapid cycling)
5. Sends a `climate.set_temperature` or `climate.turn_off` command to the heat pump **only if the state has changed** — avoids hammering the device every 60 seconds.

### Schedule integration

The schedule entity can be a standard HA `schedule` helper:

- **On/off schedule**: `on` = Comfort mode, `off` = Eco mode.
- **Schedule with `mode` attribute**: supports `comfort`, `eco`, `boost`, or `off` values directly (compatible with custom schedule integrations that expose a mode attribute).

### Force mode switches

Force modes bypass the schedule entirely. They are mutually exclusive — turning on Force Boost will automatically turn off Force Comfort and Force Eco. Turning a force switch off returns control to the schedule.

---

## Installation (HACS)

1. In HACS → Integrations → three-dot menu → Custom repositories
2. Add `https://github.com/smartthings54/smart-climate-control`
3. Category: Integration
4. After adding, click the integration → **Download** → change the branch to `v2-beta`
5. Restart Home Assistant
6. Settings → Devices & Services → Add Integration → Smart Climate Control

---

## Configuration options

All settings are adjustable after setup via the integration's gear icon:

| Setting | Default | Description |
|---|---|---|
| Comfort Temperature | 20°C | Target when in comfort mode |
| Eco Temperature | 18°C | Target when in eco mode |
| Boost Temperature | 23°C | Target when in boost mode |
| Deadband Below | 0.5°C | How far below target before heating turns ON |
| Deadband Above | 0.5°C | How far above target before heating turns OFF |
| Heating Schedule | — | Optional schedule entity for automatic mode changes |

---

## Dashboard card (basic)

```yaml
type: entities
title: Smart Climate
entities:
  - entity: switch.smart_climate_climate_management
  - entity: sensor.smart_climate_status
  - entity: sensor.smart_climate_mode
  - entity: sensor.smart_climate_target
  - entity: switch.smart_climate_force_comfort
  - entity: switch.smart_climate_force_eco
  - entity: switch.smart_climate_force_boost
  - entity: number.smart_climate_comfort_temperature
  - entity: number.smart_climate_eco_temperature
  - entity: number.smart_climate_boost_temperature
```

---

## Reporting issues

Please open issues on the [GitHub issue tracker](https://github.com/smartthings54/smart-climate-control/issues) and tag them with **v2-beta**.

Include the relevant lines from your Home Assistant log (`Settings → System → Logs`, filter by `smart_climate`).
