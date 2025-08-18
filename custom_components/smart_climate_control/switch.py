import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate Control switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    
    entities = [
        SmartClimateEnableSwitch(coordinator, config_entry),
        SmartClimateOverrideSwitch(coordinator, config_entry),
        SmartClimateForceEcoSwitch(coordinator, config_entry),
    ]
    
    async_add_entities(entities)


class SmartClimateBaseSwitch(SwitchEntity):
    """Base switch for Smart Climate Control."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, config_entry, switch_type):
        """Initialize the switch."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_{switch_type}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }


class SmartClimateEnableSwitch(SmartClimateBaseSwitch):
    """Enable switch for Smart Climate Control."""

    def __init__(self, coordinator, config_entry):
        """Initialize the enable switch."""
        super().__init__(coordinator, config_entry, "enable")
        self._attr_name = "Climate Management"
        self._attr_icon = "mdi:power"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.coordinator.enabled

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.coordinator.enabled = True
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.coordinator.enabled = False
        await self.coordinator.async_update()


class SmartClimateOverrideSwitch(SmartClimateBaseSwitch):
    """Override switch for Smart Climate Control."""

    def __init__(self, coordinator, config_entry):
        """Initialize the override switch."""
        super().__init__(coordinator, config_entry, "override")
        self._attr_name = "Manual Override"
        self._attr_icon = "mdi:account-check"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.coordinator.override_mode

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.coordinator.override_mode = True
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.coordinator.override_mode = False
        await self.coordinator.async_update()


class SmartClimateForceEcoSwitch(SmartClimateBaseSwitch):
    """Force eco switch for Smart Climate Control."""

    def __init__(self, coordinator, config_entry):
        """Initialize the force eco switch."""
        super().__init__(coordinator, config_entry, "force_eco")
        self._attr_name = "Force Eco Mode"
        self._attr_icon = "mdi:leaf"

    @property
    def is_on(self):
        """Return true if the switch is on."""
        return self.coordinator.force_eco_mode

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        self.coordinator.force_eco_mode = True
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        self.coordinator.force_eco_mode = False
        await self.coordinator.async_update()