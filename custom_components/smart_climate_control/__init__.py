"""Smart Climate Control v2 beta."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import SmartClimateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.SWITCH, Platform.NUMBER]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Smart Climate Control from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    coordinator = SmartClimateCoordinator(hass, entry)

    # Load persisted state (temps, force mode, enabled flag) before first refresh
    await coordinator.async_initialize()

    # First refresh: computes state and commands the heat pump.
    # Raises ConfigEntryNotReady if the update fails, so HA will retry.
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Re-run when the user changes options (deadband, temps, schedule entity)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Trigger a refresh when options are changed via the UI."""
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry and release control of the heat pump."""
    coordinator: SmartClimateCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Hand control back — turn the heat pump off gracefully
    await coordinator._send_off()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
