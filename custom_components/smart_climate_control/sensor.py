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
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }


class SmartClimateStatusSensor(SmartClimateBaseSensor):
    """Status sensor for Smart Climate Control."""

    def __init__(self, coordinator, config_entry):
        """Initialize the status sensor."""
        super().__init__(coordinator, config_entry, "status")
        self._attr_name = "Status"
        self._attr_icon = "mdi:information-outline"

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.coordinator.debug_text


class SmartClimateModeSensor(SmartClimateBaseSensor):
    """Mode sensor for Smart Climate Control."""
    
    def __init__(self, coordinator, config_entry):
        """Initialize the mode sensor."""
        super().__init__(coordinator, config_entry, "mode")
        self._attr_name = "Active Mode"
        self._attr_icon = "mdi:home-thermometer"
    
    @property
    def state(self):
        """Return the current mode."""
        if self.coordinator.force_eco_mode or self.coordinator.sleep_mode_active:
            return "Eco"
        elif self.coordinator.override_mode:
            return "Override"
        else:
            # Capitalize the schedule mode (handles comfort, boost, eco, off)
            mode = self.coordinator.schedule_mode
            return mode.capitalize() if mode else "Unknown"


class SmartClimateTargetSensor(SmartClimateBaseSensor):
    """Target temperature sensor for Smart Climate Control."""

    def __init__(self, coordinator, config_entry):
        """Initialize the target sensor."""
        super().__init__(coordinator, config_entry, "target_temp")
        self._attr_name = "Target Temperature"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def state(self):
        """Return the target temperature."""

        return self.coordinator.target_temperature

