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

    def __init__(self, coordinator, config_entry, switch_type, name):
        """Initialize the switch."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_{switch_type}"
        self._attr_name = name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
        }


class SmartClimateEnableSwitch(SmartClimateBaseSwitch):
    """Master enable switch for Smart Climate Control."""

    def __init__(self, coordinator, config_entry):
        """Initialize the enable switch."""
        super().__init__(coordinator, config_entry, "enable", "Climate Management")
        self._attr_icon = "mdi:robot"

    @property
    def is_on(self):
        """Return true if smart control is enabled."""
        return self.coordinator.smart_control_enabled

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        heat_pump_state = self.coordinator.current_heat_pump_state
        return {
            "controlled_entity": self.coordinator.heat_pump_entity_id,
            "heat_pump_mode": heat_pump_state.get("hvac_mode"),
            "heat_pump_temperature": heat_pump_state.get("temperature"),
            "smart_control_active": self.coordinator.smart_control_active,
        }

    async def async_turn_on(self, **kwargs):
        """Enable smart control."""
        await self.coordinator.enable_smart_control(True)

    async def async_turn_off(self, **kwargs):
        """Disable smart control."""
        await self.coordinator.enable_smart_control(False)


class SmartClimateOverrideSwitch(SmartClimateBaseSwitch):
    """Override switch - forces comfort mode when on."""

    def __init__(self, coordinator, config_entry):
        """Initialize the override switch."""
        super().__init__(coordinator, config_entry, "override", "Manual Override")
        self._attr_icon = "mdi:account-check"

    @property
    def is_on(self):
        """Return true if override is active."""
        return self.coordinator.override_mode

    @property
    def available(self):
        """Only available when smart control is enabled."""
        return self.coordinator.smart_control_enabled

    async def async_turn_on(self, **kwargs):
        """Enable override mode."""
        self.coordinator.override_mode = True
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Disable override mode."""
        self.coordinator.override_mode = False
        await self.coordinator.async_update()


class SmartClimateForceEcoSwitch(SmartClimateBaseSwitch):
    """Force eco switch."""

    def __init__(self, coordinator, config_entry):
        """Initialize the force eco switch."""
        super().__init__(coordinator, config_entry, "force_eco", "Force Eco Mode")
        self._attr_icon = "mdi:leaf"

    @property
    def is_on(self):
        """Return true if force eco is active."""
        return self.coordinator.force_eco_mode

    @property
    def available(self):
        """Only available when smart control is enabled."""
        return self.coordinator.smart_control_enabled

    async def async_turn_on(self, **kwargs):
        """Enable force eco mode."""
        self.coordinator.force_eco_mode = True
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Disable force eco mode."""
        self.coordinator.force_eco_mode = False
        await self.coordinator.async_update()
