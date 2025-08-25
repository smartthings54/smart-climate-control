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
        _LOGGER.warning(f"INIT: {self._temp_type} temperature number entity created")

    @property
    def native_value(self):
        """Return the current value."""
        if self._temp_type == "comfort":
            value = self.coordinator.comfort_temp
        elif self._temp_type == "eco":
            value = self.coordinator.eco_temp
        elif self._temp_type == "boost":
            value = self.coordinator.boost_temp
        else:
            value = None
        
        _LOGGER.warning(f"GET VALUE: {self._temp_type} = {value}°C")
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        _LOGGER.warning(f"SET VALUE CALLED: {self._temp_type} to {value}°C")
        
        # Get old value for comparison
        if self._temp_type == "comfort":
            old_value = self.coordinator.comfort_temp
            self.coordinator.comfort_temp = value
        elif self._temp_type == "eco":
            old_value = self.coordinator.eco_temp
            self.coordinator.eco_temp = value
        elif self._temp_type == "boost":
            old_value = self.coordinator.boost_temp
            self.coordinator.boost_temp = value
        else:
            old_value = None
        
        _LOGGER.warning(f"VALUE CHANGE: {self._temp_type} from {old_value}°C to {value}°C")
        
        # Save to storage with current target temperature
        try:
            storage_data = {
                "comfort_temp": self.coordinator.comfort_temp,
                "eco_temp": self.coordinator.eco_temp,
                "boost_temp": self.coordinator.boost_temp,
                "last_target": self.coordinator.target_temperature,
            }
            _LOGGER.warning(f"SAVING TO STORAGE: {storage_data}")
            await self.coordinator.store.async_save(storage_data)
            _LOGGER.warning("STORAGE SAVE COMPLETED")
        except Exception as e:
            _LOGGER.error(f"STORAGE SAVE FAILED: {e}")
        
        # Force entity state update
        try:
            self.async_write_ha_state()
            _LOGGER.warning("ENTITY STATE UPDATE COMPLETED")
        except Exception as e:
            _LOGGER.error(f"ENTITY STATE UPDATE FAILED: {e}")
        
        # Update coordinator and trigger climate control logic
        try:
            await self.coordinator.async_update()
            _LOGGER.warning("COORDINATOR UPDATE COMPLETED")
        except Exception as e:
            _LOGGER.error(f"COORDINATOR UPDATE FAILED: {e}")
        
        # Fire an event to update other entities
        try:
            self.hass.bus.async_fire(f"{DOMAIN}_temperature_changed", {
                "temp_type": self._temp_type,
                "value": value,
                "entity_id": self.entity_id,
            })
            _LOGGER.warning("EVENT FIRED COMPLETED")
        except Exception as e:
            _LOGGER.error(f"EVENT FIRE FAILED: {e}")
        
        _LOGGER.warning(f"SET VALUE COMPLETED: {self._temp_type} = {value}°C")
