import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN, 
    DEFAULT_COMFORT_TEMP, 
    DEFAULT_ECO_TEMP, 
    DEFAULT_BOOST_TEMP,
    DEFAULT_DEADBAND,
    DEFAULT_MAX_HOUSE_TEMP,
    DEFAULT_WEATHER_COMP_FACTOR,
    DEFAULT_MAX_COMP_TEMP,
    DEFAULT_MIN_COMP_TEMP
)

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate Control number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    entities = [
        # Temperature settings
        SmartClimateTemperatureNumber(coordinator, config_entry, "comfort", "Comfort Temperature", 16.0, 25.0, 0.5),
        SmartClimateTemperatureNumber(coordinator, config_entry, "eco", "Eco Temperature", 16.0, 25.0, 0.5),
        SmartClimateTemperatureNumber(coordinator, config_entry, "boost", "Boost Temperature", 16.0, 25.0, 0.5),
        
        # Control parameters
        SmartClimateControlNumber(coordinator, config_entry, "deadband_below", "Deadband Below", 0.1, 2.0, 0.1, "mdi:thermometer-minus"),
        SmartClimateControlNumber(coordinator, config_entry, "deadband_above", "Deadband Above", 0.1, 2.0, 0.1, "mdi:thermometer-plus"),
        SmartClimateControlNumber(coordinator, config_entry, "max_house_temp", "Max House Temperature", 20.0, 30.0, 0.5, "mdi:home-thermometer"),
        SmartClimateControlNumber(coordinator, config_entry, "weather_comp_factor", "Weather Compensation", 0.0, 1.0, 0.1, "mdi:weather-cloudy", None),
        SmartClimateControlNumber(coordinator, config_entry, "max_comp_temp", "Max Compensated Temp", 20.0, 30.0, 0.5, "mdi:thermometer-chevron-up"),
        SmartClimateControlNumber(coordinator, config_entry, "min_comp_temp", "Min Compensated Temp", 14.0, 20.0, 0.5, "mdi:thermometer-chevron-down"),
    ]
    
    async_add_entities(entities)


class SmartClimateTemperatureNumber(NumberEntity):
    """Temperature number entity for Smart Climate Control."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, config_entry, temp_type, name, min_val, max_val, step):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self._temp_type = temp_type
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{temp_type}_temp"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
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
        if self._temp_type == "comfort":
            self.coordinator.comfort_temp = value
        elif self._temp_type == "eco":
            self.coordinator.eco_temp = value
        elif self._temp_type == "boost":
            self.coordinator.boost_temp = value
        
        # Save to storage
        await self.coordinator.store.async_save({
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "deadband_below": self.coordinator.deadband_below,
            "deadband_above": self.coordinator.deadband_above,
            "max_house_temp": self.coordinator.max_house_temp,
            "weather_comp_factor": self.coordinator.weather_comp_factor,
        })
        
        await self.coordinator.async_update()


class SmartClimateControlNumber(NumberEntity):
    """Control parameter number entity for Smart Climate Control."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator, config_entry, param_type, name, min_val, max_val, step, icon, unit=UnitOfTemperature.CELSIUS):
        """Initialize the number entity."""
        self.coordinator = coordinator
        self._param_type = param_type
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{param_type}"
        self._attr_native_min_value = min_val
        self._attr_native_max_value = max_val
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_icon = icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }

    @property
    def native_value(self):
        """Return the current value."""
        return getattr(self.coordinator, self._param_type, None)

    async def async_set_native_value(self, value: float) -> None:
        """Set the value."""
        setattr(self.coordinator, self._param_type, value)
        
        # Save to storage
        await self.coordinator.store.async_save({
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "deadband_below": self.coordinator.deadband_below,
            "deadband_above": self.coordinator.deadband_above,
            "max_house_temp": self.coordinator.max_house_temp,
            "weather_comp_factor": self.coordinator.weather_comp_factor,
            "max_comp_temp": getattr(self.coordinator, 'max_comp_temp', DEFAULT_MAX_COMP_TEMP),
            "min_comp_temp": getattr(self.coordinator, 'min_comp_temp', DEFAULT_MIN_COMP_TEMP),
        })
        
        await self.coordinator.async_update()
