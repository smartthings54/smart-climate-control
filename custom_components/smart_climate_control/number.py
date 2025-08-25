import logging
import asyncio

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
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
    def native_value(self) -> float:
        """Return the current value."""
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
        
        # Store old value for comparison
        old_value = self.native_value
        
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
        
        # CRITICAL: Force immediate state update before anything else
        self.async_write_ha_state()
        
        # Small delay to let the state propagate
        await asyncio.sleep(0.05)
        
        # Force another state update
        self.async_write_ha_state()
        
        # Update coordinator and trigger climate control logic
        await self.coordinator.async_update()
        
        # Fire an event to notify other components
        self.hass.bus.async_fire(f"{DOMAIN}_temperature_changed", {
            "temp_type": self._temp_type,
            "old_value": old_value,
            "new_value": value,
            "entity_id": self.entity_id,
        })
        
        # Force update all entities in this integration
        await self._force_integration_refresh()
        
        _LOGGER.debug(f"Temperature {self._temp_type} updated from {old_value}°C to {value}°C")

    async def _force_integration_refresh(self):
        """Force refresh of all entities in this integration."""
        try:
            # Get all entities from this integration
            entity_registry = self.hass.helpers.entity_registry.async_get(self.hass)
            entities = [
                entry for entry in entity_registry.entities.values()
                if entry.platform == DOMAIN
            ]
            
            # Force update each entity
            for entity in entities:
                if entity.entity_id in self.hass.states.async_all():
                    entity_obj = self.hass.states.get(entity.entity_id)
                    if entity_obj:
                        # Force state update
                        self.hass.states.async_set(
                            entity.entity_id,
                            entity_obj.state,
                            entity_obj.attributes,
                            force_update=True
                        )
        except Exception as e:
            _LOGGER.debug(f"Could not force integration refresh: {e}")

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to Home Assistant."""
        # Always call parent to ensure state is written
        super().async_write_ha_state()
        
        # Also manually set the state to force UI update
        try:
            current_value = self.native_value
            self.hass.states.async_set(
                self.entity_id,
                current_value,
                {
                    **self.state_attributes,
                    "unit_of_measurement": self.unit_of_measurement,
                },
                force_update=True
            )
        except Exception as e:
            _LOGGER.debug(f"Manual state set failed: {e}")
