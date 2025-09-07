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
    
    # Order: Force Comfort, Force Eco, Manual Override, Climate Management (logical control order)
    entities = [
        SmartClimateForceComfortSwitch(coordinator, config_entry),
        SmartClimateForceEcoSwitch(coordinator, config_entry),
        SmartClimateOverrideSwitch(coordinator, config_entry),
        SmartClimateEnableSwitch(coordinator, config_entry),
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

    @property
    def available(self):
        """Entity is always available - we want to show state even when disabled."""
        return True


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
    """Force comfort switch - forces comfort mode when on."""

    def __init__(self, coordinator, config_entry):
        """Initialize the force comfort switch."""
        super().__init__(coordinator, config_entry, "override", "Force Comfort Mode")
        self._attr_icon = "mdi:home-thermometer-outline"

    @property
    def is_on(self):
        """Return true if force comfort is active."""
        return self.coordinator.override_mode

    @property
    def available(self):
        """Always available - shows current state even when smart control disabled."""
        return True

    @property
    def extra_state_attributes(self):
        """Return extra state attributes including why it might not be active."""
        attrs = {
            "force_comfort_mode": self.coordinator.override_mode,
            "smart_control_enabled": self.coordinator.smart_control_enabled,
        }
        
        # Add helpful info about why force comfort might not be effective
        if self.coordinator.override_mode and not self.coordinator.smart_control_enabled:
            attrs["note"] = "Force comfort set but smart control is disabled"
        elif not self.coordinator.override_mode:
            attrs["note"] = "Force comfort not active"
        else:
            attrs["note"] = "Force comfort active"
            
        return attrs

    async def async_turn_on(self, **kwargs):
        """Enable force comfort mode."""
        self.coordinator.override_mode = True
        # When force comfort is enabled, disable force eco
        self.coordinator.force_eco_mode = False
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Disable force comfort mode."""
        self.coordinator.override_mode = False
        await self.coordinator.async_update()


class SmartClimateForceComfortSwitch(SmartClimateBaseSwitch):
    """Force comfort switch."""

    def __init__(self, coordinator, config_entry):
        """Initialize the force comfort switch."""
        super().__init__(coordinator, config_entry, "force_comfort", "Force Comfort Mode")
        self._attr_icon = "mdi:home-thermometer-outline"

    @property
    def is_on(self):
        """Return true if force comfort is active."""
        return self.coordinator.force_comfort_mode

    @property
    def available(self):
        """Always available - shows current state even when smart control disabled."""
        return True

    @property
    def extra_state_attributes(self):
        """Return extra state attributes including why it might not be active."""
        attrs = {
            "force_comfort_mode": self.coordinator.force_comfort_mode,
            "smart_control_enabled": self.coordinator.smart_control_enabled,
        }
        
        # Add helpful info about why force comfort might not be effective
        if self.coordinator.force_comfort_mode and not self.coordinator.smart_control_enabled:
            attrs["note"] = "Force comfort set but smart control is disabled"
        elif not self.coordinator.force_comfort_mode:
            attrs["note"] = "Force comfort not active"
        else:
            attrs["note"] = "Force comfort active"
            
        return attrs

    async def async_turn_on(self, **kwargs):
        """Enable force comfort mode."""
        self.coordinator.force_comfort_mode = True
        # When force comfort is enabled, disable other force modes and override
        self.coordinator.force_eco_mode = False
        self.coordinator.override_mode = False
        await self.coordinator.async_update()

    async def async_turn_off(self, **kwargs):
        """Disable force comfort mode."""
        self.coordinator.force_comfort_mode = False
        await self.coordinator.async_update()

