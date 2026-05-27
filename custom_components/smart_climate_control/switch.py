"""Switch platform for Smart Climate Control v2 beta."""
import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
    """Set up Smart Climate switches."""
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities([
        SmartClimateEnableSwitch(coordinator, config_entry),
        SmartClimateForceComfortSwitch(coordinator, config_entry),
        SmartClimateForceEcoSwitch(coordinator, config_entry),
        SmartClimateForceBoostSwitch(coordinator, config_entry),
    ])


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class SmartClimateBaseSwitch(CoordinatorEntity, SwitchEntity):
    """Shared boilerplate for all Smart Climate switches."""

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


# ---------------------------------------------------------------------------
# Master enable switch
# ---------------------------------------------------------------------------

class SmartClimateEnableSwitch(SmartClimateBaseSwitch):
    """Master on/off for the whole smart control system."""

    _attr_icon = "mdi:robot"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "enable", "Climate Management")

    @property
    def is_on(self) -> bool:
        return self.coordinator.smart_control_enabled

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_enabled(True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_set_enabled(False)

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "controlled_entity": self.coordinator.heat_pump_entity_id,
            "current_action":    self.coordinator.current_action,
        }


# ---------------------------------------------------------------------------
# Force mode switches  (mutually exclusive — handled in coordinator)
# ---------------------------------------------------------------------------

class SmartClimateForceComfortSwitch(SmartClimateBaseSwitch):
    """Hold comfort temperature regardless of schedule."""

    _attr_icon = "mdi:home-thermometer-outline"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "force_comfort", "Force Comfort")

    @property
    def is_on(self) -> bool:
        return self.coordinator.force_mode == "comfort"

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_force_mode("comfort")

    async def async_turn_off(self, **kwargs) -> None:
        # Only clear if this switch is the active one
        if self.coordinator.force_mode == "comfort":
            await self.coordinator.async_set_force_mode(None)

    @property
    def extra_state_attributes(self) -> dict:
        return {"target_temp": self.coordinator.comfort_temp}


class SmartClimateForceEcoSwitch(SmartClimateBaseSwitch):
    """Hold eco temperature regardless of schedule."""

    _attr_icon = "mdi:leaf"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "force_eco", "Force Eco")

    @property
    def is_on(self) -> bool:
        return self.coordinator.force_mode == "eco"

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_force_mode("eco")

    async def async_turn_off(self, **kwargs) -> None:
        if self.coordinator.force_mode == "eco":
            await self.coordinator.async_set_force_mode(None)

    @property
    def extra_state_attributes(self) -> dict:
        return {"target_temp": self.coordinator.eco_temp}


class SmartClimateForceBoostSwitch(SmartClimateBaseSwitch):
    """Hold boost temperature regardless of schedule."""

    _attr_icon = "mdi:rocket-launch"

    def __init__(self, coordinator, config_entry):
        super().__init__(coordinator, config_entry, "force_boost", "Force Boost")

    @property
    def is_on(self) -> bool:
        return self.coordinator.force_mode == "boost"

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_set_force_mode("boost")

    async def async_turn_off(self, **kwargs) -> None:
        if self.coordinator.force_mode == "boost":
            await self.coordinator.async_set_force_mode(None)

    @property
    def extra_state_attributes(self) -> dict:
        return {"target_temp": self.coordinator.boost_temp}
