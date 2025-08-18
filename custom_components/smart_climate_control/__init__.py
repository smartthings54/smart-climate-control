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

from .const import (
    DOMAIN,
    CONF_HEAT_PUMP,
    CONF_ROOM_SENSOR,
    CONF_OUTSIDE_SENSOR,
    CONF_AVERAGE_SENSOR,
    CONF_DOOR_SENSOR,
    CONF_BED_SENSORS,
    CONF_COMFORT_TEMP,
    CONF_ECO_TEMP,
    CONF_BOOST_TEMP,
    CONF_DEADBAND_BELOW,
    CONF_DEADBAND_ABOVE,
    CONF_MAX_HOUSE_TEMP,
    CONF_WEATHER_COMP_FACTOR,
    CONF_MAX_COMP_TEMP,
    CONF_MIN_COMP_TEMP,
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

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]

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
    
    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Register services
    await async_setup_services(hass)
    
    # Start the control loop
    entry.async_on_unload(
        async_track_time_interval(
            hass, coordinator.async_update, timedelta(seconds=60)
        )
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    
    return unload_ok

async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Smart Climate Control."""
    
    async def handle_force_eco(call: ServiceCall) -> None:
        """Handle force eco mode service."""
        for entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            coordinator.force_eco_mode = call.data.get("enable", True)
            await coordinator.async_update()
    
    async def handle_reset_temperatures(call: ServiceCall) -> None:
        """Handle temperature reset service."""
        for entry_id in hass.data[DOMAIN]:
            coordinator = hass.data[DOMAIN][entry_id]["coordinator"]
            await coordinator.reset_temperatures()
    
    hass.services.async_register(DOMAIN, "force_eco", handle_force_eco)
    hass.services.async_register(DOMAIN, "reset_temperatures", handle_reset_temperatures)

class SmartClimateCoordinator:
    """Coordinator for Smart Climate Control."""
    
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.config = entry.data
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        
        # State variables
        self.enabled = True
        self.override_mode = False
        self.force_eco_mode = False
        self.schedule_mode = "comfort"
        self.current_action = "off"
        self.target_temperature = None
        self.last_avg_house_over_limit = False
        self.door_open_time = None
        self.sleep_mode_active = False
        self.debug_text = "System initializing..."
        
        # Temperature settings
        self.comfort_temp = self.config.get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)
        self.eco_temp = self.config.get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)
        self.boost_temp = self.config.get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP)
        
        # Control parameters
        self.deadband_below = self.config.get(CONF_DEADBAND_BELOW, DEFAULT_DEADBAND)
        self.deadband_above = self.config.get(CONF_DEADBAND_ABOVE, DEFAULT_DEADBAND)
        self.max_house_temp = self.config.get(CONF_MAX_HOUSE_TEMP, DEFAULT_MAX_HOUSE_TEMP)
        self.weather_comp_factor = self.config.get(CONF_WEATHER_COMP_FACTOR, DEFAULT_WEATHER_COMP_FACTOR)
        
    async def async_initialize(self) -> None:
        """Initialize the coordinator."""
        # Load stored data
        stored_data = await self.store.async_load()
        if stored_data:
            self.comfort_temp = stored_data.get("comfort_temp", self.comfort_temp)
            self.eco_temp = stored_data.get("eco_temp", self.eco_temp)
            self.boost_temp = stored_data.get("boost_temp", self.boost_temp)
    
    async def async_update(self, now=None) -> None:
        """Update climate control logic."""
        try:
            # Get sensor values
            room_temp = await self._get_sensor_value(self.config[CONF_ROOM_SENSOR])
            outside_temp = await self._get_sensor_value(self.config[CONF_OUTSIDE_SENSOR], 5.0)
            avg_house_temp = await self._get_sensor_value(self.config.get(CONF_AVERAGE_SENSOR))
            
            # Check door status
            door_open = await self._check_door_status()
            
            # Check sleep status
            await self._check_sleep_status()
            
            # Determine target temperature
            base_temp = self._determine_base_temperature()
            
            # Main control logic
            action, temperature, reason = await self._calculate_control(
                room_temp, outside_temp, avg_house_temp, base_temp, door_open
            )
            
            # Apply weather compensation if heating
            if action == "on" and outside_temp < 0:
                compensation = min(abs(outside_temp) * self.weather_comp_factor, 5.0)
                temperature = min(temperature + compensation, self.config.get(CONF_MAX_COMP_TEMP, DEFAULT_MAX_COMP_TEMP))
                temperature = max(temperature, self.config.get(CONF_MIN_COMP_TEMP, DEFAULT_MIN_COMP_TEMP))
                temperature = round(temperature)
            
            # Update state
            self.current_action = action
            self.target_temperature = temperature
            self.debug_text = self._format_debug_text(
                action, temperature, room_temp, avg_house_temp, outside_temp, reason
            )
            
            # Control heat pump
            await self._control_heat_pump(action, temperature)
            
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
    
    def _determine_base_temperature(self) -> float:
        """Determine the base target temperature."""
        if self.force_eco_mode or self.sleep_mode_active:
            return self.eco_temp
        elif self.override_mode:
            return self.comfort_temp
        elif self.schedule_mode == "eco":
            return self.eco_temp
        elif self.schedule_mode == "boost":
            return self.boost_temp
        else:
            return self.comfort_temp
    
    async def _calculate_control(
        self, room_temp: Optional[float], outside_temp: float,
        avg_house_temp: Optional[float], base_temp: float, door_open: bool
    ) -> tuple[str, Optional[float], str]:
        """Calculate control action and temperature."""
        # Check basic conditions
        if not self.enabled:
            return "off", None, "System disabled"
        
        if door_open:
            return "off", None, "Door open"
        
        if self.override_mode:
            return "on", base_temp, "Manual override"
        
        # Check house average temperature limit
        if avg_house_temp is not None:
            if self.last_avg_house_over_limit:
                if avg_house_temp > (self.max_house_temp - 0.5):
                    return "off", None, "House temp limit"
            elif avg_house_temp > self.max_house_temp:
                self.last_avg_house_over_limit = True
                return "off", None, "House temp limit"
            else:
                self.last_avg_house_over_limit = False
        
        # Check room temperature
        if room_temp is None:
            return "off", None, "No room temp data"
        
        # Deadband control
        turn_on_temp = base_temp - self.deadband_below
        turn_off_temp = base_temp + self.deadband_above
        
        if room_temp <= turn_on_temp:
            return "on", base_temp, f"Heating needed ({room_temp:.1f}°C <= {turn_on_temp:.1f}°C)"
        elif room_temp >= turn_off_temp:
            return "off", None, f"Too hot ({room_temp:.1f}°C >= {turn_off_temp:.1f}°C)"
        else:
            # In deadband - maintain current state
            return self.current_action, self.target_temperature if self.current_action == "on" else None, "In deadband"
    
# Updated section for __init__.py - replace the _control_heat_pump method with this:

    async def _control_heat_pump(self, action: str, temperature: Optional[float]) -> None:
        """Control the heat pump entity."""
        heat_pump = self.config.get(CONF_HEAT_PUMP)
        if not heat_pump:
            return
        
        # Get current state of heat pump
        heat_pump_state = self.hass.states.get(heat_pump)
        if not heat_pump_state:
            return
            
        current_hvac_mode = heat_pump_state.state
        current_temp = heat_pump_state.attributes.get('temperature')
        
        if action == "on" and temperature is not None:
            # Only send command if something needs to change
            if current_hvac_mode != "heat" or current_temp != temperature:
                _LOGGER.debug(f"Changing heat pump: mode={current_hvac_mode}->heat, temp={current_temp}->{temperature}")
                await self.hass.services.async_call(
                    "climate",
                    "set_temperature",
                    {
                        "entity_id": heat_pump,
                        "temperature": temperature,
                        "hvac_mode": "heat",
                    },
                    blocking=False,
                )
            else:
                _LOGGER.debug(f"Heat pump already at correct settings: heat mode, {temperature}°C")
                
        elif action == "off":
            # Only turn off if it's currently on
            if current_hvac_mode != "off":
                _LOGGER.debug(f"Turning off heat pump (was {current_hvac_mode})")
                await self.hass.services.async_call(
                    "climate",
                    SERVICE_TURN_OFF,
                    {"entity_id": heat_pump},
                    blocking=False,
                )
            else:
                _LOGGER.debug("Heat pump already off")

# Alternative simpler fix - add state tracking to the coordinator class
# Add these lines to the __init__ method of SmartClimateCoordinator class:

        # Add to existing state variables in __init__
        self.last_sent_action = None
        self.last_sent_temperature = None

# Then modify _control_heat_pump to check before sending:

    async def _control_heat_pump(self, action: str, temperature: Optional[float]) -> None:
        """Control the heat pump entity."""
        heat_pump = self.config.get(CONF_HEAT_PUMP)
        if not heat_pump:
            return
        
        # Check if we need to send a command
        if action == self.last_sent_action and temperature == self.last_sent_temperature:
            _LOGGER.debug(f"No change needed: {action} at {temperature}°C")
            return
            
        # Update last sent values
        self.last_sent_action = action
        self.last_sent_temperature = temperature
        
        if action == "on" and temperature is not None:
            _LOGGER.info(f"Setting heat pump to heat mode at {temperature}°C")
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": heat_pump,
                    "temperature": temperature,
                    "hvac_mode": "heat",
                },
                blocking=False,
            )
        elif action == "off":
            _LOGGER.info(f"Turning off heat pump")
            await self.hass.services.async_call(
                "climate",
                SERVICE_TURN_OFF,
                {"entity_id": heat_pump},
                blocking=False,
            )
    
    def _format_debug_text(
        self, action: str, temperature: Optional[float],
        room_temp: Optional[float], avg_house_temp: Optional[float],
        outside_temp: float, reason: str
    ) -> str:
        """Format debug text for display."""
        room_str = f"{room_temp:.1f}" if room_temp is not None else "N/A"
        avg_str = f"{avg_house_temp:.1f}" if avg_house_temp is not None else "N/A"
        
        if action == "off":
            return f"OFF | R: {room_str}°C | H: {avg_str}°C | O: {outside_temp:.1f}°C | {reason}"
        else:
            mode = "Eco" if self.force_eco_mode or self.sleep_mode_active else "Comfort"
            return f"ON | {mode} {temperature}°C | R: {room_str}°C | H: {avg_str}°C | O: {outside_temp:.1f}°C | {reason}"
    
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
        })
        
        # Update

        await self.async_update()
