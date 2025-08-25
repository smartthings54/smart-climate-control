import logging
import asyncio

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

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


class SmartClimateTemperatureNumber(NumberEntity, RestoreEntity):
    """Temperature number entity for Smart Climate Control."""

    _attr_has_entity_name = True
    _attr_native_min_value = 16.0
    _attr_native_max_value = 25.0
    _attr_native_step = 0.5
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER
    _attr_should_poll = False

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
        self._cached_value = None

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added to hass."""
        await super().async_added_to_hass()
        
        # Listen for coordinator updates
        self.async_on_remove(
            self.coordinator.entry.add_update_listener(self._handle_coordinator_update)
        )
        
        # Set initial cached value
        self._cached_value = self.native_value

    async def _handle_coordinator_update(self, entry):
        """Handle coordinator updates."""
        old_value = self._cached_value
        new_value = self.native_value
        if old_value != new_value:
            self._cached_value = new_value
            self.async_write_ha_state()

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

    @property 
    def state(self) -> float:
        """Return the state of the entity."""
        return self.native_value

    async def async_set_native_value(self, value: float) -> None:
        """Set the value via dashboard slider."""
        await self._update_temperature(value, "dashboard_slider")

    async def async_set_value(self, value: float) -> None:
        """Set the value via service call.""" 
        await self._update_temperature(value, "service_call")

    async def _update_temperature(self, value: float, source: str) -> None:
        """Update temperature value from any source."""
        _LOGGER.debug(f"Setting {self._temp_type} temperature to {value}°C from {source}")
        
        # Update coordinator values
        old_value = self.native_value
        if self._temp_type == "comfort":
            self.coordinator.comfort_temp = value
        elif self._temp_type == "eco":
            self.coordinator.eco_temp = value
        elif self._temp_type == "boost":
            self.coordinator.boost_temp = value
        
        # Update cached value immediately
        self._cached_value = value
        
        # Save to storage with current target temperature
        await self.coordinator.store.async_save({
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "last_target": self.coordinator.target_temperature,
        })
        
        # Force immediate state update
        self.async_write_ha_state()
        
        # Update coordinator and trigger climate control logic
        await self.coordinator.async_update()
        
        # Fire an event to update other entities
        self.hass.bus.async_fire(f"{DOMAIN}_temperature_changed", {
            "temp_type": self._temp_type,
            "old_value": old_value,
            "new_value": value,
            "entity_id": self.entity_id,
            "source": source,
        })
        
        # Schedule another state update to ensure UI refreshes
        self.hass.async_create_task(self._delayed_state_update())
        
        _LOGGER.debug(f"Temperature {self._temp_type} updated from {old_value}°C to {value}°C via {source}")

    async def _delayed_state_update(self):
        """Force a delayed state update to ensure UI consistency."""
        await asyncio.sleep(0.5)
        self.async_write_ha_state()

    @callback
    def async_write_ha_state(self) -> None:
        """Write the state to the state machine."""
        # Update cached value before writing state
        self._cached_value = self.native_value
        super().async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        return {
            "temp_type": self._temp_type,
            "source": "Smart Climate Control",
            "last_updated": self.hass.states.get(self.entity_id).last_updated if self.hass.states.get(self.entity_id) else None,
        }
