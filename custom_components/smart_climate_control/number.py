import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_COMFORT_TEMP, DEFAULT_ECO_TEMP, DEFAULT_BOOST_TEMP

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate Control number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    entities = [
        SmartClimateTemperatureNumber(coordinator, config_entry, "comfort", "Comfort Temperature", DEFAULT_COMFORT_TEMP),
        SmartClimateTemperatureNumber(coordinator, config_entry, "eco", "Eco Temperature", DEFAULT_ECO_TEMP),
        SmartClimateTemperatureNumber(coordinator, config_entry, "boost", "Boost Temperature", DEFAULT_BOOST_TEMP),
    ]
    
    async_add_entities(entities)


class SmartClimateTemperatureNumber(NumberEntity):
    """Temperature number entity for Smart Climate Control."""

    _attr_has_entity_name = True
    _attr_native_min_value = 16.0
    _attr_native_max_value = 25.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, config_entry, temp_type, name, default):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self._temp_type = temp_type
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{temp_type}_temp"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }
        self._attr_icon = "mdi:thermometer"
        # Store the current value to prevent snap-back
        self._current_value = None

    async def async_added_to_hass(self):
        """When entity is added to hass."""
        await super().async_added_to_hass()
        
        # Initialize current value from coordinator
        if self._temp_type == "comfort":
            self._current_value = self.coordinator.comfort_temp
        elif self._temp_type == "eco":
            self._current_value = self.coordinator.eco_temp
        elif self._temp_type == "boost":
            self._current_value = self.coordinator.boost_temp

    @property
    def native_value(self) -> float:
        """Return the current value."""
        # Return our stored value if we have it, otherwise get from coordinator
        if self._current_value is not None:
            return self._current_value
            
        if self._temp_type == "comfort":
            return self.coordinator.comfort_temp
        elif self._temp_type == "eco":
            return self.coordinator.eco_temp
        elif self._temp_type == "boost":
            return self.coordinator.boost_temp
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value via dashboard slider or service call."""
        _LOGGER.debug(f"Setting {self._temp_type} temperature to {value}°C")

        # Store the new value immediately to prevent snap-back
        self._current_value = value

        # Update coordinator values
        if self._temp_type == "comfort":
            self.coordinator.comfort_temp = value
        elif self._temp_type == "eco":
            self.coordinator.eco_temp = value
        elif self._temp_type == "boost":
            self.coordinator.boost_temp = value

        # Force Home Assistant to update the state immediately
        self.async_write_ha_state()

        try:
            # Save to storage
            await self.coordinator.store.async_save({
                "comfort_temp": self.coordinator.comfort_temp,
                "eco_temp": self.coordinator.eco_temp,
                "boost_temp": self.coordinator.boost_temp,
                "last_target": self.coordinator.target_temperature,
            })

            # Trigger coordinator update
            await self.coordinator.async_update()
            
            _LOGGER.debug(f"Temperature {self._temp_type} updated to {value}°C successfully")
            
        except Exception as e:
            _LOGGER.error(f"Failed to update {self._temp_type} temperature: {e}")

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        coordinator_value = None
        if self._temp_type == "comfort":
            coordinator_value = self.coordinator.comfort_temp
        elif self._temp_type == "eco":
            coordinator_value = self.coordinator.eco_temp
        elif self._temp_type == "boost":
            coordinator_value = self.coordinator.boost_temp
            
        return {
            "temp_type": self._temp_type,
            "current_value": self._current_value,
            "coordinator_value": coordinator_value,
        }
