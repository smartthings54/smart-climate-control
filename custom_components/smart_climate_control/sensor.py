"""Sensor platform for Smart Climate Control v2 beta."""
import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import SmartClimateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate sensors."""
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        SmartClimateStatusSensor(coordinator, config_entry),
        SmartClimateModeSensor(coordinator, config_entry),
        SmartClimateTargetSensor(coordinator, config_entry),
    ])


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class SmartClimateBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class: wires up CoordinatorEntity and shared device info."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SmartClimateCoordinator,
        config_entry: ConfigEntry,
        key: str,
        name: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{config_entry.entry_id}_{key}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Smart Climate",
            "model": "Smart Climate Controller v2",
        }

    @property
    def _data(self) -> dict:
        """Shorthand for coordinator.data with empty-dict fallback."""
        return self.coordinator.data or {}


# ---------------------------------------------------------------------------
# Status sensor  —  human-readable debug line + key attributes
# ---------------------------------------------------------------------------

class SmartClimateStatusSensor(SmartClimateBaseSensor):
    """Shows what the system is currently doing and why."""

    _attr_icon = "mdi:information-outline"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "status", "Status")

    @property
    def native_value(self) -> str:
        return self._data.get("debug_text", "Initialising...")

    @property
    def extra_state_attributes(self) -> dict:
        d = self._data
        return {
            "smart_control_enabled": d.get("smart_control_enabled"),
            "action":                d.get("action"),
            "room_temp":             d.get("room_temp"),
            "target_temp":           d.get("target_temp"),
            "deadband_below":        d.get("deadband_below"),
            "deadband_above":        d.get("deadband_above"),
            "controlled_entity":     self.coordinator.heat_pump_entity_id,
        }


# ---------------------------------------------------------------------------
# Mode sensor  —  what mode is active right now
# ---------------------------------------------------------------------------

class SmartClimateModeSensor(SmartClimateBaseSensor):
    """Shows the active mode: Comfort, Eco, Boost, or a Force override."""

    _attr_icon = "mdi:home-thermometer"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "mode", "Mode")

    @property
    def native_value(self) -> str:
        d = self._data
        if not d.get("smart_control_enabled"):
            return "Disabled"
        force = d.get("force_mode")
        if force:
            return f"Force {force.title()}"
        schedule = d.get("schedule_mode", "comfort")
        return schedule.title()

    @property
    def extra_state_attributes(self) -> dict:
        d = self._data
        return {
            "force_mode":    d.get("force_mode"),
            "schedule_mode": d.get("schedule_mode"),
            "enabled":       d.get("smart_control_enabled"),
        }


# ---------------------------------------------------------------------------
# Target sensor  —  the temperature the system is working towards
# ---------------------------------------------------------------------------

class SmartClimateTargetSensor(SmartClimateBaseSensor):
    """Shows the current target temperature (respects force modes + schedule)."""

    _attr_icon = "mdi:thermometer-plus"
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "target_temp", "Target")

    @property
    def native_value(self) -> float | None:
        return self._data.get("target_temp")

    @property
    def extra_state_attributes(self) -> dict:
        d = self._data
        return {
            "comfort_temp": d.get("comfort_temp"),
            "eco_temp":     d.get("eco_temp"),
            "boost_temp":   d.get("boost_temp"),
            "active_mode":  d.get("active_mode"),
        }
