import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate Control sensors."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    entities = [
        SmartClimateStatusSensor(coordinator, config_entry),
        SmartClimateModeSensor(coordinator, config_entry),
        SmartClimateTargetSensor(coordinator, config_entry),
        # Removed SmartClimateControlledEntitySensor - not providing useful info
    ]
    
    async_add_entities(entities)


class SmartClimateBaseSensor(SensorEntity):
    """Base sensor for Smart Climate Control."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, sensor_type, name):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }

    @property
    def available(self):
        """Sensors are always available - we want to show state even when disabled."""
        return True


class SmartClimateStatusSensor(SmartClimateBaseSensor):
    """Status sensor showing current smart control logic."""

    def __init__(self, coordinator, config_entry):
        """Initialize the status sensor."""
        super().__init__(coordinator, config_entry, "status", "Status")
        self._attr_icon = "mdi:information-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        if not self.coordinator.smart_control_enabled:
            return "Smart control disabled"
        return self.coordinator.debug_text

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        heat_pump_state = self.coordinator.current_heat_pump_state
        return {
            "smart_control_enabled": self.coordinator.smart_control_enabled,
            "controlled_entity": self.coordinator.heat_pump_entity_id,
            "heat_pump_mode": heat_pump_state.get("hvac_mode"),
            "heat_pump_action": heat_pump_state.get("hvac_action"),
            "heat_pump_temperature": heat_pump_state.get("temperature"),
            "heat_pump_current_temp": heat_pump_state.get("current_temperature"),
        }


class SmartClimateModeSensor(SmartClimateBaseSensor):
    """Mode sensor showing what mode smart control is using."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the mode sensor."""
        super().__init__(coordinator, config_entry, "mode", "Mode")
        self._attr_icon = "mdi:home-thermometer"
    
    @property
    def state(self):
        """Return the current smart control mode."""
        if not self.coordinator.smart_control_enabled:
            return "Disabled"
            
        if self.coordinator.force_comfort_mode:
            return "Force Comfort"
        elif self.coordinator.force_eco_mode or self.coordinator.sleep_mode_active:
            return "Force Eco" if self.coordinator.force_eco_mode else "Sleep Eco"
        elif self.coordinator.override_mode:
            return "Override (Comfort)"
        else:
            mode = self.coordinator.schedule_mode
            return mode.capitalize() if mode else "Unknown"

    @property
    def extra_state_attributes(self):
        """Return mode details."""
        return {
            "smart_control_enabled": self.coordinator.smart_control_enabled,
            "force_comfort": self.coordinator.force_comfort_mode,
            "force_eco": self.coordinator.force_eco_mode,
            "sleep_active": self.coordinator.sleep_mode_active,
            "override_active": self.coordinator.override_mode,
            "schedule_mode": self.coordinator.schedule_mode,
        }

class SmartClimateTargetSensor(SmartClimateBaseSensor):
    """Target temperature sensor showing what smart control is targeting."""

    def __init__(self, coordinator, config_entry):
        """Initialize the target sensor."""
        super().__init__(coordinator, config_entry, "target_temp", "Target")
        self._attr_icon = "mdi:thermometer-plus"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the target temperature that smart control would use."""
        # Always return what the target would be, even if disabled
        base_temp = self.coordinator._determine_base_temperature()
        return base_temp

    @property
    def extra_state_attributes(self):
        """Return temperature details."""
        return {
            "smart_control_enabled": self.coordinator.smart_control_enabled,
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "active_mode": self._get_active_mode(),
        }
    
    def _get_active_mode(self) -> str:
        """Get the active temperature mode."""
        if not self.coordinator.smart_control_enabled:
            return "disabled"
        elif self.coordinator.force_comfort_mode:
            return "force_comfort"
        elif self.coordinator.force_eco_mode or self.coordinator.sleep_mode_active:
            return "force_eco" if self.coordinator.force_eco_mode else "sleep_eco"
        elif self.coordinator.override_mode:
            return "comfort"
        else:
            return self.coordinator.schedule_mode
