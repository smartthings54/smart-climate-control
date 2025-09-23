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

    async def async_added_to_hass(self):
        """Restore last state."""
        await super().async_added_to_hass()
        
        # Restore previous state
        if (last_state := await self.async_get_last_state()) is not None:
            if last_state.state in [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]:
                self._attr_hvac_mode = last_state.state
                # IMPORTANT: Also update coordinator state based on restored climate state
                if last_state.state == HVACMode.OFF:
                    self.coordinator.smart_control_enabled = False
                else:
                    self.coordinator.smart_control_enabled = True
                    if last_state.state == HVACMode.HEAT:
                        self.coordinator.override_mode = True
                        # Clear force eco when restoring to force comfort
                        self.coordinator.force_eco_mode = False
                    else:
                        self.coordinator.override_mode = False
                        
            if (temp := last_state.attributes.get(ATTR_TEMPERATURE)) is not None:
                self._attr_target_temperature = float(temp)

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current operation mode."""
        if not self.coordinator.smart_control_enabled:
            return HVACMode.OFF
        elif self.coordinator.override_mode:
            return HVACMode.HEAT
        else:
            return HVACMode.AUTO

    @property
    def hvac_action(self) -> HVACAction:
        """Return the current running hvac operation."""
        if not self.coordinator.smart_control_enabled or self.coordinator.current_action == "off":
            return HVACAction.OFF
        return HVACAction.HEATING

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
        if not self.coordinator.smart_control_enabled:
            # Return the stored target temperature when disabled, not None
            return self._attr_target_temperature
        return self.coordinator._determine_base_temperature()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return entity specific state attributes."""
        return {
            "status": self.coordinator.debug_text,
            "active_mode": self._get_active_mode(),
            "force_comfort": self.coordinator.override_mode,
            "force_eco": self.coordinator.force_eco_mode,
            "sleep_active": self.coordinator.sleep_mode_active,
            "comfort_temp": self.coordinator.comfort_temp,
            "eco_temp": self.coordinator.eco_temp,
            "boost_temp": self.coordinator.boost_temp,
            "smart_control_enabled": self.coordinator.smart_control_enabled,
            "deadband_below": self.coordinator.deadband_below,
            "deadband_above": self.coordinator.deadband_above,
            "max_house_temp": self.coordinator.max_house_temp,
            "weather_comp_factor": self.coordinator.weather_comp_factor,
        }

    def _get_active_mode(self) -> str:
        """Get the active temperature mode."""
        if not self.coordinator.smart_control_enabled:
            return "disabled"
        elif self.coordinator.override_mode:
            return "force_comfort"
        elif self.coordinator.force_eco_mode or self.coordinator.sleep_mode_active:
            return "force_eco" if self.coordinator.force_eco_mode else "sleep_eco"
        else:
            return self.coordinator.schedule_mode

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temperature
            # Update coordinator based on mode
            if self._get_active_mode() == "eco":
                self.coordinator.eco_temp = temperature
            elif self._get_active_mode() == "boost":
                self.coordinator.boost_temp = temperature
            else:
                self.coordinator.comfort_temp = temperature
            
            # Save to storage
            await self.coordinator.store.async_save({
                "comfort_temp": self.coordinator.comfort_temp,
                "eco_temp": self.coordinator.eco_temp,
                "boost_temp": self.coordinator.boost_temp,
                "smart_control_enabled": self.coordinator.smart_control_enabled,
            })
            
            await self.coordinator.async_update()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new target hvac mode."""
        _LOGGER.info(f"Climate entity: Setting HVAC mode to {hvac_mode}")
        self._attr_hvac_mode = hvac_mode
        
        if hvac_mode == HVACMode.OFF:
            # Disable smart control through coordinator
            await self.coordinator.enable_smart_control(False)
        else:
            # Enable smart control through coordinator
            await self.coordinator.enable_smart_control(True)
            
            # Remember the last active mode (HEAT or AUTO)
            if hvac_mode in [HVACMode.HEAT, HVACMode.AUTO]:
                self._attr_last_active_mode = hvac_mode
            
            # FIXED: Clear conflicting force modes and set override mode properly
            if hvac_mode == HVACMode.HEAT:
                # Force comfort mode - clear force eco and set override
                self.coordinator.override_mode = True
                self.coordinator.force_eco_mode = False
                _LOGGER.info("Climate: Set to HEAT mode - force comfort active, force eco cleared")
            else:  # AUTO mode
                # Auto mode - clear both force modes
                self.coordinator.override_mode = False
                self.coordinator.force_eco_mode = False
                _LOGGER.info("Climate: Set to AUTO mode - both force modes cleared")
                
        await self.coordinator.async_update()

    async def async_turn_on(self) -> None:
        """Turn the entity on."""
        # Use the last active mode, default to AUTO
        last_mode = getattr(self, '_attr_last_active_mode', HVACMode.AUTO)
        await self.async_set_hvac_mode(last_mode)

    async def async_turn_off(self) -> None:
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)
