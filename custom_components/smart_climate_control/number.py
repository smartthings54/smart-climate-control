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
        # Store local value to prevent snap-back
        self._local_value = None

    @property
    def native_value(self) -> float:
        """Return the current value."""
        # If we have a local value from recent slider change, use it
        if self._local_value is not None:
            return self._local_value
            
        # Otherwise get from coordinator
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
        
        # IMMEDIATELY set local value to prevent slider snap-back
        self._local_value = value
        
        # Update coordinator values SYNCHRONOUSLY to prevent timing issues
        if self._temp_type == "comfort":
            self.coordinator.comfort_temp = value
        elif self._temp_type == "eco":
            self.coordinator.eco_temp = value
        elif self._temp_type == "boost":
            self.coordinator.boost_temp = value
        
        # Clear local value now that coordinator is updated
        self._local_value = None
        
        # Immediately write state to prevent UI flickering
        self.async_write_ha_state()
        
        # Save to storage
        try:
            await self.coordinator.store.async_save({
                "comfort_temp": self.coordinator.comfort_temp,
                "eco_temp": self.coordinator.eco_temp,
                "boost_temp": self.coordinator.boost_temp,
                "last_target": self.coordinator.target_temperature,
            })
        except Exception as e:
            _LOGGER.error(f"Failed to save to storage: {e}")
        
        # Update coordinator and trigger climate control logic
        try:
            await self.coordinator.async_update()
        except Exception as e:
            _LOGGER.error(f"Failed to update coordinator: {e}")
        
        _LOGGER.debug(f"Temperature {self._temp_type} updated to {value}°C successfully")

    async def async_update(self) -> None:
        """Update the entity."""
        # Don't override if we have a pending local value
        if self._local_value is None:
            # Just trigger a state write with current coordinator values
            self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "temp_type": self._temp_type,
            "coordinator_value": getattr(self.coordinator, f"{self._temp_type}_temp"),
            "local_value": self._local_value,
        }
