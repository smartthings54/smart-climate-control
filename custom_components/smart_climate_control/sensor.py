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
        SmartClimateControlledEntitySensor(coordinator, config_entry),
    ]
    
    async_add_entities(entities)


class SmartClimateBaseSensor(SensorEntity):
    """Base sensor for Smart Climate Control."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, sensor_type):
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_{sensor_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": f"Smart Control for {config_entry.data.get('name', 'Heat Pump')}",
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }


class SmartClimateStatusSensor(SmartClimateBaseSensor):
    """Status sensor showing current smart control logic."""

    def __init__(self, coordinator, config_entry):
        """Initialize the status sensor."""
        super().__init__(coordinator, config_entry, "status")
        self._attr_name = "Smart Control Status"
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
        super().__init__(coordinator, config_entry, "mode")
        self._attr_name = "Smart Control Mode"
        self._attr_icon = "mdi:home-thermometer"
    
    @property
    def state(self):
        """Return the current smart control mode."""
        if not self.coordinator.smart_control_enabled:
            return "Disabled"
            
        if self.coordinator.force_eco_mode or self.coordinator.sleep_mode_active:
            return "Eco"
        elif self.coordinator.override_mode:
            return "Override (Comfort)"
        else:
            mode = self.coordinator.schedule_mode
            return mode.capitalize() if mode else "Unknown"

    @property
    def extra_state_attributes(self):
        """Return mode details."""
        return {
            "force_eco": self.coordinator.force_eco_mode,
            "sleep_active": self.coordinator.sleep_mode_active,
            "override_active": self.coordinator.override_mode,
            "schedule_mode": self.coordinator.schedule_mode,
        }


class SmartClimateTargetSensor(SmartClimateBaseSensor):
    """Target temperature sensor showing what smart control is targeting."""

    def __init__(self, coordinator, config_entry):
        """Initialize the target sensor."""
        super().__init__(coordinator, config_entry, "target_temp")
        self._attr_name = "Smart Control Target"
        self._attr_icon = "mdi:thermometer-plus"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the target temperature that smart control is using."""
        if not self.coordinator.smart_control_enabled:
            return None
            
        # Return the temperature we're actually targeting
        base_temp = self.coordinator._determine_base_temperature()
        return base_temp

    @property
    def extra_state_attributes(self):
        """Return temperature details."""
        return {
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
        }


class SmartClimateControlledEntitySensor(SmartClimateBaseSensor):
    """Sensor showing which entity is being controlled."""

    def __init__(self, coordinator, config_entry):
        """Initialize the controlled entity sensor."""
        super().__init__(coordinator, config_entry, "controlled_entity")
        self._attr_name = "Controlled Heat Pump"
        self._attr_icon = "mdi:thermostat"

    @property
    def state(self):
        """Return the controlled entity ID."""
        return self.coordinator.heat_pump_entity_id

    @property
    def extra_state_attributes(self):
        """Return controlled entity state."""
        heat_pump_state = self.coordinator.current_heat_pump_state
        return {
            "entity_id": self.coordinator.heat_pump_entity_id,
            "current_mode": heat_pump_state.get("hvac_mode"),
            "current_action": heat_pump_state.get("hvac_action"),
            "current_temperature": heat_pump_state.get("temperature"),
            "room_temperature": heat_pump_state.get("current_temperature"),
            "smart_control_active": self.coordinator.smart_control_active,
        }
