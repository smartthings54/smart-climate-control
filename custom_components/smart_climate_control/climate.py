import logging
from typing import Any, List, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Smart Climate Control climate entity."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    async_add_entities([SmartClimateEntity(coordinator, config_entry)])


class SmartClimateEntity(ClimateEntity, RestoreEntity):
    """Representation of Smart Climate Control."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.TURN_ON
    )

    def __init__(self, coordinator, config_entry):
        """Initialize the climate entity."""
        self.coordinator = coordinator
        self._attr_unique_id = f"{config_entry.entry_id}_climate"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": config_entry.data.get("name", "Smart Climate Control"),
            "manufacturer": "Custom",
            "model": "Smart Climate Controller",
            "sw_version": "1.0.0",
        }
        self._attr_hvac_mode = HVACMode.AUTO
        self._attr_target_temperature = coordinator.comfort_temp
        self._attr_current_temperature = None
        self._last_active_mode = HVACMode.AUTO

    async def async_added_to_hass(self):
        """Restore last state."""
        await super().async_added_to_hass()
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]:
                self._attr_hvac_mode = last_state.state
                # Store the last active mode if it wasn't OFF
                if last_state.state in [HVACMode.HEAT, HVACMode.AUTO]:
                    self._last_active_mode = last_state.state
            if (temp := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(temp)

        # Listen for coordinator updates
        self.coordinator.hass.bus.async_listen(
            f"{DOMAIN}_state_updated",
            self._handle_coordinator_update
        )

    async def _handle_coordinator_update(self, event):
        """Handle coordinator state updates."""
        if event.data.get("entry_id") == self.coordinator.entry.entry_id:
            # Force entity state update
            self.async_write_ha_state()

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if not self.coordinator.enabled:
            return HVACMode.OFF
        return self._attr_hvac_mode

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if not self.coordinator.enabled:
            return HVACAction.OFF
        
        # Use coordinator's current action to determine HVAC action
        if self.coordinator.current_action == "on":
            return HVACAction.HEATING
        else:
            return HVACAction.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        room_sensor = self.coordinator.config.get("room_sensor")
        if room_sensor:
            state = self.hass.states.get(room_sensor)
            if state and state.state not in ["unknown", "unavailable"]:
                try:
                    return float(state.state)
                except ValueError:
                    pass
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the temperature we try to reach."""
        return self.coordinator.target_temperature

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "status": self.coordinator.debug_text,
            "active_mode": self._get_active_mode(),
            "force_eco": self.coordinator.force_eco_mode,
            "override": self.coordinator.override_mode,
            "sleep_active": self.coordinator.sleep_mode_active,
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "deadband_below": self.coordinator.deadband_below,
            "deadband_above": self.coordinator.deadband_above,
            "schedule_mode": self.coordinator.schedule_mode,
            "current_action": self.coordinator.current_action,
            "weather_comp_factor": self.coordinator.weather_comp_factor,
            "max_house_temp": self.coordinator.max_house_temp,
            "heat_pump_entity": self.coordinator.config.get("heat_pump", "None"),
        }

    def _get_active_mode(self) -> str:
        """Get the active temperature mode."""
        if self.coordinator.force_eco_mode or self.coordinator.sleep_mode_active:
            return "eco"
        elif self.coordinator.override_mode:
            return "comfort"
        elif self.coordinator.schedule_mode == "boost":
            return "boost"
        elif self.coordinator.schedule_mode == "eco":
            return "eco"
        elif self.coordinator.schedule_mode == "off":
            return "off"
        else:
            return "comfort"

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temperature
            
            # Update the appropriate temperature setting based on current mode
            active_mode = self._get_active_mode()
            if active_mode == "eco":
                self.coordinator.eco_temp = temperature
            elif active_mode == "boost":
                self.coordinator.boost_temp = temperature
            else:  # comfort or override
                self.coordinator.comfort_temp = temperature
            
            # Save to storage
            await self.coordinator.store.async_save({
                "comfort_temp": self.coordinator.comfort_temp,
                "eco_temp": self.coordinator.eco_temp,
                "boost_temp": self.coordinator.boost_temp,
                "last_target": temperature,
            })
            
            await self.coordinator.async_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        old_mode = self._attr_hvac_mode
        self._attr_hvac_mode = hvac_mode
        
        _LOGGER.info(f"HVAC mode change: {old_mode} -> {hvac_mode}")
        
        if hvac_mode == HVACMode.OFF:
            self.coordinator.enabled = False
            self.coordinator.override_mode = False
        else:
            self.coordinator.enabled = True
            # Remember the last active mode
            if hvac_mode in [HVACMode.HEAT, HVACMode.AUTO]:
                self._last_active_mode = hvac_mode
            
            if hvac_mode == HVACMode.HEAT:
                # Manual heat mode = override
                self.coordinator.override_mode = True
            else:  # AUTO mode
                # Auto mode = follow schedule
                self.coordinator.override_mode = False
                
        await self.coordinator.async_update()
        # Force immediate state update
        self.async_write_ha_state()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        # Use the last active mode, default to AUTO
        await self.async_set_hvac_mode(self._last_active_mode)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
