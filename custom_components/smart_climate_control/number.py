"""Number platform for Smart Climate Control v2 beta."""
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, DEFAULT_COMFORT_TEMP, DEFAULT_ECO_TEMP, DEFAULT_BOOST_TEMP

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate temperature number entities."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        SmartClimateTempNumber(coordinator, config_entry, "comfort", "Comfort Temperature", DEFAULT_COMFORT_TEMP),
        SmartClimateTempNumber(coordinator, config_entry, "eco",     "Eco Temperature",     DEFAULT_ECO_TEMP),
        SmartClimateTempNumber(coordinator, config_entry, "boost",   "Boost Temperature",   DEFAULT_BOOST_TEMP),
    ])


class SmartClimateTempNumber(CoordinatorEntity, NumberEntity):
    """Adjustable temperature setpoint for one heating mode."""

    _attr_has_entity_name = True
    _attr_native_step = 0.5
    _attr_native_min_value = 16.0
    _attr_native_max_value = 25.0
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:thermometer"

    def __init__(self, coordinator, config_entry, temp_type: str, name: str, default: float) -> None:
        super().__init__(coordinator)
        self._temp_type = temp_type
        self._attr_name = name
        self._attr_unique_id = f"{config_entry.entry_id}_{temp_type}_temp"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Smart Climate",
            "model": "Smart Climate Controller v2",
        }

    @property
    def native_value(self) -> float | None:
        """Return the current setpoint from the coordinator."""
        return getattr(self.coordinator, f"{self._temp_type}_temp", None)

    async def async_set_native_value(self, value: float) -> None:
        """Update the setpoint and trigger an immediate recalculation."""
        await self.coordinator.async_set_temperature(self._temp_type, value)
