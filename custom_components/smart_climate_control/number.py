import logging
import asyncio

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

    @property
    def native_value(self):
        """Return the current value."""
        if self._temp_type == "comfort":
            return self.coordinator.comfort_temp
        elif self._temp_type == "eco":
            return self.coordinator.eco_temp
        elif self._temp_type == "boost":
            return self.coordinator.boost_temp
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        _LOGGER.debug(f"Setting {self._temp_type} temperature to {value}°C")
        
        # Update coordinator values
        if self._temp_type == "comfort":
            self.coordinator.comfort_temp = value
        elif self._temp_type == "eco":
            self.coordinator.eco_temp = value
        elif self._temp_type == "boost":
            self.coordinator.boost_temp = value
        
        # Save to storage with current target temperature
        await self.coordinator.store.async_save({
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "last_target": self.coordinator.target_temperature,
        })
        
        # Update coordinator and trigger climate control logic
        await self.coordinator.async_update()
        
        # Force entity state update with a small delay
        self.async_write_ha_state()
        
        # Give HA a moment to process, then force another state update
        await asyncio.sleep(0.1)
        self.async_write_ha_state()
        
        # Fire an event to update other entities
        self.hass.bus.async_fire(f"{DOMAIN}_temperature_changed", {
            "temp_type": self._temp_type,
            "value": value,
            "entity_id": self.entity_id,
        })
        
        # Force update of all related entities
        await asyncio.sleep(0.1)
        for entity_id in [
            f"number.{self.coordinator.entry.entry_id}_comfort_temp",
            f"number.{self.coordinator.entry.entry_id}_eco_temp", 
            f"number.{self.coordinator.entry.entry_id}_boost_temp",
            f"climate.{self.coordinator.entry.entry_id}_climate"
        ]:
            if entity_id in self.hass.states.async_all():
                self.hass.states.async_set(entity_id, self.hass.states.get(entity_id).state, force_update=True)
        
        _LOGGER.debug(f"Temperature {self._temp_type} updated to {value}°C successfully")
