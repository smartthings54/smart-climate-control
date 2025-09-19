import logging
import asyncio
from datetime import timedelta
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    Platform,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    ATTR_TEMPERATURE,
)
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.helpers.entity_platform import async_get_platforms
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    DOMAIN,
    CONF_HEAT_PUMP,
    CONF_ROOM_SENSOR,
    CONF_OUTSIDE_SENSOR,
    CONF_AVERAGE_SENSOR,
    CONF_DOOR_SENSOR,
    CONF_BED_SENSORS,
    CONF_SCHEDULE_ENTITY,
    CONF_COMFORT_TEMP,
    CONF_ECO_TEMP,
    CONF_BOOST_TEMP,
    CONF_DEADBAND_BELOW,
    CONF_DEADBAND_ABOVE,
    CONF_MAX_HOUSE_TEMP,
    CONF_WEATHER_COMP_FACTOR,
    CONF_MAX_COMP_TEMP,
    CONF_MIN_COMP_TEMP,
    CONF_PRESENCE_TRACKER,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_ECO_TEMP,
    DEFAULT_BOOST_TEMP,
    DEFAULT_DEADBAND,
    DEFAULT_MAX_HOUSE_TEMP,
    DEFAULT_WEATHER_COMP_FACTOR,
    DEFAULT_MAX_COMP_TEMP,
    DEFAULT_MIN_COMP_TEMP,
)

_LOGGER = logging.getLogger(__name__)

# Try different platform order for entity ordering
PLATFORMS = [Platform.NUMBER, Platform.SWITCH, Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Climate Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create coordinator for this entry
    coordinator = SmartClimateCoordinator(hass, entry)
    await coordinator.async_initialize()
    
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "entry": entry,
    }
    
    # Set up platforms - back to the original method for safety
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Create device link to controlled climate entity
    await _setup_device_links(hass, entry)
    
    # Register services
    await async_setup_services(hass)
    
    # Start the control loop
    entry.async_on_unload(
        async_track_time_interval(
            hass, coordinator.async_update, timedelta(seconds=60)
        )
    )
    
    return True

async def _setup_device_links(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Set up device links by moving heat pump entity to our device."""
    # Wait for entity registry to be ready
    await asyncio.sleep(1)
    
    entity_reg = er.async_get(hass)
    device_reg = dr.async_get(hass)
    
    # Get our Smart Climate device
    our_device = device_reg.async_get_device(
        identifiers={(DOMAIN, entry.entry_id)}
    )
    
    if not our_device:
        _LOGGER.error("Smart Climate Control device not found - this shouldn't happen")
        return
    
    # Get the heat pump entity
    heat_pump_entity_id = entry.data[CONF_HEAT_PUMP]
    _LOGGER.info(f"Looking for heat pump entity: {heat_pump_entity_id}")
    
    heat_pump_entity = entity_reg.async_get(heat_pump_entity_id)
    
    if not heat_pump_entity:
        _LOGGER.error(f"Heat pump entity {heat_pump_entity_id} not found in entity registry")
        return
    
    _LOGGER.info(f"Found heat pump entity: {heat_pump_entity_id}, current device: {heat_pump_entity.device_id}")
    
    # Store the original device ID for potential restoration
    original_device_id = heat_pump_entity.device_id
    
    # Get area from original device if it exists
    original_area = None
    if original_device_id:
        original_device = device_reg.async_get(original_device_id)
        if original_device:
            original_area = original_device.area_id
            _LOGGER.info(f"Heat pump original device: {original_device.name}, area: {original_area}")
    
    # Move the heat pump entity to our device
    try:
        entity_reg.async_update_entity(
            heat_pump_entity_id,
            device_id=our_device.id,
        )
        _LOGGER.info(f"SUCCESS: Moved heat pump entity {heat_pump_entity_id} to Smart Climate device")
        
        # Update our device with the area from the heat pump
        if original_area:
            device_reg.async_update_device(
                our_device.id,
                suggested_area=original_area,
            )
            _LOGGER.info(f"Updated Smart Climate device area to: {original_area}")
                
    except Exception as e:
        _LOGGER.error(f"FAILED to move heat pump entity: {e}")
        return
    
    # Store the original device ID in coordinator for potential restoration
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    coordinator.original_heat_pump_device_id = original_device_id
    
    _LOGGER.info(f"Device linking complete - heat pump entity should now appear in Smart Climate Control device")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Make sure we release control when unloading
        coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        await coordinator._release_control()
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Smart Climate Control."""
    
    async def handle_force_eco(call: ServiceCall) -> None:
        """Handle force eco mode service."""
        for entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            coordinator.force_eco_mode = call.data.get("enable", True)
            # If enabling force eco, disable force comfort
            if coordinator.force_eco_mode:
                coordinator.force_comfort_mode = False
            await coordinator.async_update()
    
    async def handle_force_comfort(call: ServiceCall) -> None:
        """Handle force comfort mode service."""
        for entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            coordinator.force_comfort_mode = call.data.get("enable", True)
            # If enabling force comfort, disable force eco
            if coordinator.force_comfort_mode:
                coordinator.force_eco_mode = False
            await coordinator.async_update()
    
    async def handle_reset_temperatures(call: ServiceCall) -> None:
        """Handle temperature reset service."""
        for entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            await coordinator.reset_temperatures()
    
    hass.services.async_register(DOMAIN, "force_eco", handle_force_eco)
    hass.services.async_register(DOMAIN, "force_comfort", handle_force_comfort)
    hass.services.async_register(DOMAIN, "reset_temperatures", handle_reset_temperatures)

class SmartClimateCoordinator:
    """Coordinator for Smart Climate Control that directly controls specified heat pump."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.config = entry.data
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        
        # The heat pump entity we'll control directly
        self.heat_pump_entity_id = self.config[CONF_HEAT_PUMP]
        
        # State variables
        self.smart_control_enabled = True
        self.override_mode = False
        self.force_eco_mode = False
        self.force_comfort_mode = False
        self.schedule_mode = "comfort"
        self.current_action = "off"
        self.last_avg_house_over_limit = False
        self.door_open_time = None
        self.sleep_mode_active = False
        self.debug_text = "System initializing..."
        self.smart_control_active = False
        
        # Tracking variables for heat pump control
        self.last_sent_action = None
        self.last_sent_temperature = None
        
        # Temperature settings
        self.comfort_temp = self.config.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)
        self.eco_temp = self.config.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)
        self.boost_temp = self.config.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP)
        
        # Register options update listener for instant updates
        self.entry.add_update_listener(self.async_options_updated)
    
    def _get_config_value(self, key: str, default: Any) -> Any:
        """Get value from options (preferred) or config (fallback)."""
        if key in self.entry.options:
            return self.entry.options[key]
        return self.config.get(key, default)
    
    @property
    def deadband_below(self) -> float:
        return self._get_config_value(CONF_DEADBAND_BELOW, DEFAULT_DEADBAND)
    
    @property
    def deadband_above(self) -> float:
        return self._get_config_value(CONF_DEADBAND_ABOVE, DEFAULT_DEADBAND)
    
    @property
    def max_house_temp(self) -> float:
        return self._get_config_value(CONF_MAX_HOUSE_TEMP, DEFAULT_MAX_HOUSE_TEMP)
    
    @property
    def weather_comp_factor(self) -> float:
        return self._get_config_value(CONF_WEATHER_COMP_FACTOR, DEFAULT_WEATHER_COMP_FACTOR)
    
    @property
    def max_comp_temp(self) -> float:
        return self._get_config_value(CONF_MAX_COMP_TEMP, DEFAULT_MAX_COMP_TEMP)
    
    @property
    def min_comp_temp(self) -> float:
        return self._get_config_value(CONF_MIN_COMP_TEMP, DEFAULT_MIN_COMP_TEMP)
    
    @staticmethod
    async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Handle options update - trigger immediate update."""
        if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
            await coordinator.async_update()
    
    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        # Load stored data
        stored_data = await self.store.async_load()
        if stored_data:
            self.comfort_temp = stored_data.get("comfort_temp", self.comfort_temp)
            self.eco_temp = stored_data.get("eco_temp", self.eco_temp)
            self.boost_temp = stored_data.get("boost_temp", self.boost_temp)
            # IMPORTANT: Restore the smart_control_enabled state
            self.smart_control_enabled = stored_data.get("smart_control_enabled", True)
            
        _LOGGER.info(f"Smart Climate Control initialized - enabled: {self.smart_control_enabled}")
    
    async def async_update(self, now=None) -> None:
        """Update climate control logic."""
        try:
            # Only control if smart control is enabled
            if not self.smart_control_enabled:
                if self.smart_control_active:
                    await self._release_control()
                return
            
            # Mark that smart control is active
            self.smart_control_active = True
            
            # Get sensor values
            room_temp = await self._get_sensor_value(self.config[CONF_ROOM_SENSOR])
            outside_temp = await self._get_sensor_value(self.config[CONF_OUTSIDE_SENSOR], 5.0)
            avg_house_temp = await self._get_sensor_value(self.config.get(CONF_AVERAGE_SENSOR))
            
            # Check door status
            door_open = await self._check_door_status()
            
            # Check sleep status
            await self._check_sleep_status()
            
            # Check schedule status
            await self._check_schedule_status()
            
            # Determine target temperature
            base_temp = self._determine_base_temperature()
            
            # Main control logic
            action, temperature, reason = await self._calculate_control(
                room_temp, outside_temp, avg_house_temp, base_temp, door_open
            )
            
            # Track weather compensation
            weather_compensation = 0
            original_temperature = temperature
            
            # Apply weather compensation if heating
            if action == "on" and outside_temp < 0 and temperature is not None:
                weather_compensation = min(abs(outside_temp) * self.weather_comp_factor, 5.0)
                temperature = min(temperature + weather_compensation, self.config.get(CONF_MAX_COMP_TEMP, DEFAULT_MAX_COMP_TEMP))
                temperature = max(temperature, self.config.get(CONF_MIN_COMP_TEMP, DEFAULT_MIN_COMP_TEMP))
                temperature = round(temperature)
            
            # Update state
            self.current_action = action
            
            self.debug_text = self._format_debug_text(
                action, temperature, room_temp, avg_house_temp, outside_temp, reason,
                original_temperature, weather_compensation
            )
            
            # Control heat pump directly
            await self._control_heat_pump_directly(action, temperature)
            
            # Fire event for state update
            self.hass.bus.async_fire(f"{DOMAIN}_state_updated", {
                "entry_id": self.entry.entry_id,
                "action": action,
                "temperature": temperature,
                "debug": self.debug_text,
            })
            
        except Exception as e:
            _LOGGER.error(f"Error in climate control update: {e}")
            self.debug_text = f"Error: {str(e)}"
    
    async def _get_sensor_value(self, entity_id: str, default: Optional[float] = None) -> Optional[float]:
        """Get sensor value with validation."""
        if not entity_id:
            return default
        
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ["unknown", "unavailable"]:
            return default
        
        try:
            value = float(state.state)
            if -50 <= value <= 50:
                return value
        except (ValueError, TypeError):
            pass
        
        return default
    
    async def _check_door_status(self) -> bool:
        """Check if door has been open too long."""
        door_sensor = self.config.get(CONF_DOOR_SENSOR)
        if not door_sensor:
            return False
        
        state = self.hass.states.get(door_sensor)
        if state and state.state == "on":
            if self.door_open_time is None:
                self.door_open_time = self.hass.loop.time()
            elif self.hass.loop.time() - self.door_open_time > 70:  # 70 seconds
                return True
        else:
            self.door_open_time = None
        
        return False
 
    async def _check_sleep_status(self) -> None:
        """Check if sleep mode should be active."""
        bed_sensors = self.config.get(CONF_BED_SENSORS, [])
        if len(bed_sensors) >= 2:
            bed1 = self.hass.states.get(bed_sensors[0])
            bed2 = self.hass.states.get(bed_sensors[1])
            
            if bed1 and bed2:
                self.sleep_mode_active = (bed1.state == "on" and bed2.state == "on")
    
    async def _check_schedule_status(self) -> None:
        """Check schedule entity for current mode."""
        schedule_entity = self.config.get(CONF_SCHEDULE_ENTITY)
        if not schedule_entity:
            self.schedule_mode = "comfort"
            return
        
        state = self.hass.states.get(schedule_entity)
        if not state:
            self.schedule_mode = "comfort"
            return
        
        # Check if schedule has a mode attribute
        if "mode" in state.attributes:
            mode = state.attributes.get("mode", "comfort")
            valid_modes = ["comfort", "eco", "boost", "off"]
            if mode.lower() in valid_modes:
                self.schedule_mode = mode.lower()
            else:
                self.schedule_mode = "comfort"
        else:
            # Fallback to old logic if no mode attribute
            if state.state == "on":
                self.schedule_mode = "comfort"
            else:
                self.schedule_mode = "eco"
            
    async def _check_presence_status(self) -> bool:
        """Check if someone is home based on presence tracker."""
        presence_tracker = self.config.get(CONF_PRESENCE_TRACKER)
        if not presence_tracker:
            return True
        
        state = self.hass.states.get(presence_tracker)
        if not state:
            _LOGGER.warning(f"Presence tracker {presence_tracker} not found")
            return True
        
        state_value = str(state.state).lower().strip()
        entity_domain = presence_tracker.split('.')[0]
        
        if entity_domain in ['device_tracker', 'person']:
            return state_value not in ['away', 'not_home', 'unknown', 'unavailable']
        elif entity_domain == 'zone':
            try:
                return int(state.state) > 0
            except:
                return state_value not in ['0', 'unknown', 'unavailable']
        elif entity_domain == 'sensor':
            if state_value in ['home', 'on', 'true', '1']:
                return True
            elif state_value in ['away', 'not_home', 'not home', 'off', 'false', '0', 'unknown', 'unavailable']:
                return False
            else:
                _LOGGER.warning(f"Unknown presence state: {state.state}")
                return True
        elif entity_domain == 'input_boolean':
            return state_value == 'on'
        elif entity_domain == 'group':
            return state_value in ['on', 'home']
        else:
            return state_value not in ['away', 'not_home', 'not home', 'off', '0', 'false', 'unknown', 'unavailable']
 
    def _determine_base_temperature(self) -> float:
        """Determine the base target temperature."""
        # Force modes take highest priority
        if self.force_comfort_mode:
            return self.comfort_temp
        elif self.force_eco_mode or self.sleep_mode_active:
            return self.eco_temp
        elif self.override_mode:
            return self.comfort_temp
        elif self.schedule_mode == "eco":
            return self.eco_temp
        elif self.schedule_mode == "boost":
            return self.boost_temp
        elif self.schedule_mode == "off":
            return self.comfort_temp
        else:
            return self.comfort_temp
    
    async def _calculate_control(
        self, room_temp: Optional[float], outside_temp: float,
        avg_house_temp: Optional[float], base_temp: float, door_open: bool
    ) -> tuple[str, Optional[float], str]:
        """Calculate control action and temperature."""
        # Check basic conditions
        if door_open:
            return "off", base_temp, "Door open"
        
        if self.override_mode:
            return "on", base_temp, "Manual override"
            
        # Check presence
        someone_home = await self._check_presence_status()
        if not someone_home:
            return "off", base_temp, "Nobody home"
        
        # Check if schedule is off
        if self.schedule_mode == "off" and not self.force_eco_mode:
            return "off", base_temp, "Schedule off"
        
        # Check house average temperature limit
        if avg_house_temp is not None:
            if self.last_avg_house_over_limit:
                if avg_house_temp > (self.max_house_temp - 0.5):
                    return "off", base_temp, "House temp limit"
            elif avg_house_temp > self.max_house_temp:
                self.last_avg_house_over_limit = True
                return "off", base_temp, "House temp limit"
            else:
                self.last_avg_house_over_limit = False
        
        # Check room temperature
        if room_temp is None:
            return "off", base_temp, "No room temp data"
        
        # Deadband control
        turn_on_temp = base_temp - self.deadband_below
        turn_off_temp = base_temp + self.deadband_above
        
        if room_temp <= turn_on_temp:
            return "on", base_temp, f"Heating needed ({room_temp:.1f}°C <= {turn_on_temp:.1f}°C)"
        elif room_temp >= turn_off_temp:
            return "off", base_temp, f"Too hot ({room_temp:.1f}°C >= {turn_off_temp:.1f}°C)"
        else:
            return self.current_action, base_temp, "In deadband"
    
    async def _control_heat_pump_directly(self, action: str, temperature: Optional[float]) -> None:
        """Control the heat pump entity directly."""
        # Check if we need to send a command (prevents unnecessary commands)
        if action == self.last_sent_action and temperature == self.last_sent_temperature:
            return
            
        # Get current state of heat pump
        heat_pump_state = self.hass.states.get(self.heat_pump_entity_id)
        if not heat_pump_state:
            _LOGGER.error(f"Heat pump entity {self.heat_pump_entity_id} not found")
            return
            
        current_hvac_mode = heat_pump_state.state
        current_temp = heat_pump_state.attributes.get('temperature')
        
        # Update last sent values
        self.last_sent_action = action
        self.last_sent_temperature = temperature
        
        if action == "on" and temperature is not None:
            # Only send command if something needs to change
            if current_hvac_mode != "heat" or current_temp != temperature:
                _LOGGER.debug(f"Smart control: Setting {self.heat_pump_entity_id} to heat at {temperature}°C")
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": self.heat_pump_entity_id,
                        "temperature": temperature,
                        "hvac_mode": "heat",
                    },
                    blocking=False,
                )
                
        elif action == "off":
            # Only turn off if it's currently on
            if current_hvac_mode != "off":
                _LOGGER.debug(f"Smart control: Turning off {self.heat_pump_entity_id}")
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_TURN_OFF,
                    {"entity_id": self.heat_pump_entity_id},
                    blocking=False,
                )
    
    async def _release_control(self) -> None:
        """Release control back to manual operation."""
        _LOGGER.info(f"Smart climate control releasing control of {self.heat_pump_entity_id}")
        
        # Actually turn off the heat pump when releasing control
        heat_pump_state = self.hass.states.get(self.heat_pump_entity_id)
        if heat_pump_state and heat_pump_state.state != "off":
            _LOGGER.info(f"Turning off heat pump {self.heat_pump_entity_id} as smart control is disabled")
            await self.hass.services.async_call(
                "climate",
                "turn_off",
                {"entity_id": self.heat_pump_entity_id},
                blocking=False,
            )
        
        self.smart_control_active = False
        self.last_sent_action = None
        self.last_sent_temperature = None
        self.current_action = "off"
        self.debug_text = "Smart control disabled"
    
    def _format_debug_text(
        self, action: str, temperature: Optional[float],
        room_temp: Optional[float], avg_house_temp: Optional[float],
        outside_temp: float, reason: str,
        original_temperature: Optional[float] = None, weather_compensation: float = 0
    ) -> str:
        """Format debug text for display."""
        room_str = f"{room_temp:.1f}" if room_temp is not None else "N/A"
        avg_str = f"{avg_house_temp:.1f}" if avg_house_temp is not None else "N/A"
        
        if action == "off":
            return f"OFF | R: {room_str}°C | H: {avg_str}°C | O: {outside_temp:.1f}°C | {reason}"
        else:
            # Determine the mode
            if self.override_mode:
                mode = "Force Comfort"
            elif self.force_eco_mode or self.sleep_mode_active:
                mode = "Force Eco" if self.force_eco_mode else "Sleep Eco"
            elif self.schedule_mode == "boost":
                mode = "Boost"
            elif self.schedule_mode == "eco":
                mode = "Eco"
            else:
                mode = "Comfort"
            
            # Add weather compensation info if applied
            temp_str = f"{temperature}°C"
            if weather_compensation > 0 and original_temperature is not None:
                temp_str = f"{temperature}°C (B:{original_temperature}°C +{weather_compensation:.1f}°C)"
            
            # Clean up the reason text - remove temperature comparisons
            clean_reason = reason
            if "Heating needed (" in reason:
                clean_reason = "Heating needed"
            elif "Too hot (" in reason:
                clean_reason = "Too hot"
                
            return f"ON | {mode} {temp_str} | R: {room_str}°C | H: {avg_str}°C | O: {outside_temp:.1f}°C | {clean_reason}"
    
    async def enable_smart_control(self, enable: bool) -> None:
        """Enable or disable smart control."""
        _LOGGER.info(f"Smart control {'enabled' if enable else 'disabled'} via coordinator")
        self.smart_control_enabled = enable
        
        # Save state immediately
        await self.store.async_save({
            "comfort_temp": self.comfort_temp,
            "eco_temp": self.eco_temp,
            "boost_temp": self.boost_temp,
            "smart_control_enabled": self.smart_control_enabled,
        })
        
        # If disabling, make sure we release control
        if not enable:
            await self._release_control()
        
        await self.async_update()
    
    @property
    def current_heat_pump_state(self) -> dict:
        """Get current state of the controlled heat pump."""
        state = self.hass.states.get(self.heat_pump_entity_id)
        if state:
            return {
                "hvac_mode": state.state,
                "temperature": state.attributes.get("temperature"),
                "current_temperature": state.attributes.get("current_temperature"),
                "hvac_action": state.attributes.get("hvac_action"),
            }
        return {}
    
    async def reset_temperatures(self) -> None:
        """Reset temperatures to defaults."""
        self.comfort_temp = DEFAULT_COMFORT_TEMP
        self.eco_temp = DEFAULT_ECO_TEMP
        self.boost_temp = DEFAULT_BOOST_TEMP
        
        # Save to storage
        await self.store.async_save({
            "comfort_temp": self.comfort_temp,
            "eco_temp": self.eco_temp,
            "boost_temp": self.boost_temp,
            "smart_control_enabled": self.smart_control_enabled,
        })
        
        # Update
        await self.async_update()


