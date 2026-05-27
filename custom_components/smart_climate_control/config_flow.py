"""Config flow for Smart Climate Control v2 beta."""
import logging
from typing import Any, Dict, Optional

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_HEAT_PUMP,
    CONF_ROOM_SENSOR,
    CONF_SCHEDULE_ENTITY,
    CONF_COMFORT_TEMP,
    CONF_ECO_TEMP,
    CONF_BOOST_TEMP,
    CONF_DEADBAND_BELOW,
    CONF_DEADBAND_ABOVE,
    DEFAULT_COMFORT_TEMP,
    DEFAULT_ECO_TEMP,
    DEFAULT_BOOST_TEMP,
    DEFAULT_DEADBAND_BELOW,
    DEFAULT_DEADBAND_ABOVE,
)

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reusable selector factories
# ---------------------------------------------------------------------------

def _temp_selector(min_val: float = 16.0, max_val: float = 25.0):
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=min_val, max=max_val, step=0.5,
            mode="slider", unit_of_measurement="°C",
        )
    )


def _deadband_selector():
    return selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=0.1, max=2.0, step=0.1,
            mode="slider", unit_of_measurement="°C",
        )
    )


def _schedule_selector():
    return selector.EntitySelector(
        selector.EntitySelectorConfig(domain="schedule")
    )


# ---------------------------------------------------------------------------
# Config flow (initial setup wizard)
# ---------------------------------------------------------------------------

class SmartClimateConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Two-step setup: (1) pick entities, (2) set temperatures."""

    VERSION = 1

    def __init__(self):
        self._data: Dict[str, Any] = {}

    # Step 1 — required / optional entities
    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        """Select the heat pump, room sensor, and optional schedule."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            # Validate required entities actually exist in HA right now
            for field in (CONF_HEAT_PUMP, CONF_ROOM_SENSOR):
                if not self.hass.states.get(user_input[field]):
                    errors[field] = "entity_not_found"

            if not errors:
                self._data = user_input
                return await self.async_step_temps()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_NAME, default="Smart Climate"): str,
                vol.Required(CONF_HEAT_PUMP): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Required(CONF_ROOM_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(CONF_SCHEDULE_ENTITY): _schedule_selector(),
            }),
            errors=errors,
        )

    # Step 2 — temperature setpoints + deadband
    async def async_step_temps(self, user_input: Optional[Dict[str, Any]] = None):
        """Configure temperature setpoints and deadband values."""
        if user_input is not None:
            self._data.update(user_input)
            return self.async_create_entry(
                title=self._data[CONF_NAME],
                data=self._data,
            )

        return self.async_show_form(
            step_id="temps",
            data_schema=vol.Schema({
                vol.Optional(CONF_COMFORT_TEMP, default=DEFAULT_COMFORT_TEMP): _temp_selector(),
                vol.Optional(CONF_ECO_TEMP, default=DEFAULT_ECO_TEMP): _temp_selector(),
                vol.Optional(CONF_BOOST_TEMP, default=DEFAULT_BOOST_TEMP): _temp_selector(),
                vol.Optional(CONF_DEADBAND_BELOW, default=DEFAULT_DEADBAND_BELOW): _deadband_selector(),
                vol.Optional(CONF_DEADBAND_ABOVE, default=DEFAULT_DEADBAND_ABOVE): _deadband_selector(),
            }),
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SmartClimateOptionsFlow(config_entry)


# ---------------------------------------------------------------------------
# Options flow (gear icon after setup)
# ---------------------------------------------------------------------------

class SmartClimateOptionsFlow(config_entries.OptionsFlow):
    """Adjust temperatures, deadband, and schedule entity after initial setup."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
        """Show the options form."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        # Pull current values: options first, then initial config, then default
        def get(key, default):
            return self.config_entry.options.get(
                key, self.config_entry.data.get(key, default)
            )

        # Build schema — schedule entity is optional so handle None default carefully
        schema: Dict[Any, Any] = {
            vol.Optional(CONF_COMFORT_TEMP, default=get(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)): _temp_selector(),
            vol.Optional(CONF_ECO_TEMP, default=get(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)): _temp_selector(),
            vol.Optional(CONF_BOOST_TEMP, default=get(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP)): _temp_selector(),
            vol.Optional(CONF_DEADBAND_BELOW, default=get(CONF_DEADBAND_BELOW, DEFAULT_DEADBAND_BELOW)): _deadband_selector(),
            vol.Optional(CONF_DEADBAND_ABOVE, default=get(CONF_DEADBAND_ABOVE, DEFAULT_DEADBAND_ABOVE)): _deadband_selector(),
        }

        # Only set a default for schedule if one is already configured
        current_schedule = get(CONF_SCHEDULE_ENTITY, None)
        if current_schedule:
            schema[vol.Optional(CONF_SCHEDULE_ENTITY, default=current_schedule)] = _schedule_selector()
        else:
            schema[vol.Optional(CONF_SCHEDULE_ENTITY)] = _schedule_selector()

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
        )
