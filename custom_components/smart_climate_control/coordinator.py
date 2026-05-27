"""Smart Climate Control coordinator."""
import logging
from datetime import timedelta
from typing import Any, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

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

STORAGE_VERSION = 1


class SmartClimateCoordinator(DataUpdateCoordinator):
    """Coordinator for Smart Climate Control.

    Handles the 60-second update cycle, deadband heating logic,
    and all communication with the heat pump entity.
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialise the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )
        self.entry = entry
        self.config = entry.data
        self.store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")

        self.heat_pump_entity_id: str = self.config[CONF_HEAT_PUMP]

        # --- Mutable state ---
        # These are set by switches/numbers and persist between update cycles.
        self.smart_control_enabled: bool = True
        self.force_mode: Optional[str] = None   # "comfort" | "eco" | "boost" | None

        # Deadband state: remembered between cycles so we don't flap on/off
        self.current_action: str = "off"        # "on" | "off"

        # Temperature setpoints (may be overridden by stored values in async_initialize)
        self.comfort_temp: float = self._get_option(CONF_COMFORT_TEMP, DEFAULT_COMFORT_TEMP)
        self.eco_temp: float = self._get_option(CONF_ECO_TEMP, DEFAULT_ECO_TEMP)
        self.boost_temp: float = self._get_option(CONF_BOOST_TEMP, DEFAULT_BOOST_TEMP)

        # Optimisation: avoid hammering the heat pump with repeated identical commands
        self._last_sent_action: Optional[str] = None
        self._last_sent_temperature: Optional[float] = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_option(self, key: str, default: Any) -> Any:
        """Return value from options (highest priority), then config data, then default."""
        return self.entry.options.get(key, self.config.get(key, default))

    @property
    def deadband_below(self) -> float:
        """Degrees below target at which heating turns ON."""
        return self._get_option(CONF_DEADBAND_BELOW, DEFAULT_DEADBAND_BELOW)

    @property
    def deadband_above(self) -> float:
        """Degrees above target at which heating turns OFF."""
        return self._get_option(CONF_DEADBAND_ABOVE, DEFAULT_DEADBAND_ABOVE)

    @property
    def schedule_entity(self) -> Optional[str]:
        """Entity ID of the schedule helper, or None."""
        return self._get_option(CONF_SCHEDULE_ENTITY, None)

    # ------------------------------------------------------------------
    # Initialisation / storage
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:
        """Load persisted state from storage."""
        stored = await self.store.async_load()
        if stored:
            self.comfort_temp = stored.get("comfort_temp", self.comfort_temp)
            self.eco_temp = stored.get("eco_temp", self.eco_temp)
            self.boost_temp = stored.get("boost_temp", self.boost_temp)
            self.smart_control_enabled = stored.get("smart_control_enabled", True)
            self.force_mode = stored.get("force_mode", None)
            _LOGGER.debug(
                "Loaded stored state: enabled=%s, force_mode=%s",
                self.smart_control_enabled,
                self.force_mode,
            )

    async def _async_save(self) -> None:
        """Persist current state to storage."""
        await self.store.async_save({
            "comfort_temp": self.comfort_temp,
            "eco_temp": self.eco_temp,
            "boost_temp": self.boost_temp,
            "smart_control_enabled": self.smart_control_enabled,
            "force_mode": self.force_mode,
        })

    # ------------------------------------------------------------------
    # Core update cycle (called every 60 s by DataUpdateCoordinator)
    # ------------------------------------------------------------------

    async def _async_update_data(self) -> dict:
        """Compute heating state and command the heat pump.

        Returns a dict consumed by all sensor / switch / number entities.
        """
        try:
            # --- Smart control disabled ---
            if not self.smart_control_enabled:
                if self.current_action == "on":
                    await self._send_off()
                return self._build_data(
                    action="off",
                    target_temp=self.comfort_temp,
                    active_mode="disabled",
                    debug_text="Smart control disabled",
                    room_temp=None,
                    schedule_mode="comfort",
                )

            # --- Gather inputs ---
            room_temp = self._read_sensor(self.config[CONF_ROOM_SENSOR])
            schedule_mode = self._read_schedule()

            # --- Determine target temperature ---
            target_temp = self._determine_target(schedule_mode)

            # --- Deadband heating logic ---
            action, reason = self._calculate_action(room_temp, target_temp, schedule_mode)

            # --- Send command to heat pump (only if something changed) ---
            await self._apply_action(action, target_temp)
            self.current_action = action

            # --- Build debug string for Status sensor ---
            active_mode = self.force_mode or schedule_mode
            debug_text = self._build_debug(action, target_temp, room_temp, active_mode, reason)

            return self._build_data(
                action=action,
                target_temp=target_temp,
                active_mode=active_mode,
                debug_text=debug_text,
                room_temp=room_temp,
                schedule_mode=schedule_mode,
            )

        except Exception as exc:
            _LOGGER.error("Error in Smart Climate update: %s", exc)
            raise UpdateFailed(f"Update failed: {exc}") from exc

    # ------------------------------------------------------------------
    # Logic helpers
    # ------------------------------------------------------------------

    def _read_sensor(self, entity_id: str) -> Optional[float]:
        """Return a sensor state as float, or None if unavailable."""
        if not entity_id:
            return None
        state = self.hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            value = float(state.state)
            # Sanity-check: temperatures outside -50 to 60 °C are bogus
            return value if -50 <= value <= 60 else None
        except (ValueError, TypeError):
            return None

    def _read_schedule(self) -> str:
        """Return schedule mode: 'comfort' | 'eco' | 'boost' | 'off'."""
        if not self.schedule_entity:
            return "comfort"

        state = self.hass.states.get(self.schedule_entity)
        if not state:
            _LOGGER.warning("Schedule entity %s not found", self.schedule_entity)
            return "comfort"

        # Some schedule integrations expose a 'mode' attribute
        if "mode" in state.attributes:
            mode = str(state.attributes["mode"]).lower()
            if mode in ("comfort", "eco", "boost", "off"):
                return mode
            _LOGGER.warning("Unrecognised schedule mode '%s', defaulting to comfort", mode)
            return "comfort"

        # Plain on/off schedule → on = comfort, off = eco
        return "comfort" if state.state == "on" else "eco"

    def _determine_target(self, schedule_mode: str) -> float:
        """Pick the target temperature based on active force mode or schedule."""
        if self.force_mode == "comfort":
            return self.comfort_temp
        if self.force_mode == "eco":
            return self.eco_temp
        if self.force_mode == "boost":
            return self.boost_temp
        if schedule_mode == "eco":
            return self.eco_temp
        if schedule_mode == "boost":
            return self.boost_temp
        # comfort or any unrecognised value → comfort temp
        return self.comfort_temp

    def _calculate_action(
        self,
        room_temp: Optional[float],
        target_temp: float,
        schedule_mode: str,
    ) -> tuple[str, str]:
        """Apply deadband logic; return (action, reason) tuple.

        Deadband behaviour:
          - Turn ON  when room_temp ≤ (target − deadband_below)
          - Turn OFF when room_temp ≥ (target + deadband_above)
          - Hold current state while inside the band
        """
        # Schedule is off and no force mode override → stay off
        if schedule_mode == "off" and self.force_mode is None:
            return "off", "Schedule off"

        if room_temp is None:
            return "off", "No room temperature"

        turn_on_at = round(target_temp - self.deadband_below, 1)
        turn_off_at = round(target_temp + self.deadband_above, 1)

        if room_temp <= turn_on_at:
            return "on", f"Room {room_temp:.1f}°C ≤ {turn_on_at:.1f}°C"
        if room_temp >= turn_off_at:
            return "off", f"Room {room_temp:.1f}°C ≥ {turn_off_at:.1f}°C"

        # Inside the deadband — hold whatever we were doing
        return self.current_action, "In deadband"

    # ------------------------------------------------------------------
    # Heat pump commands
    # ------------------------------------------------------------------

    async def _apply_action(self, action: str, temperature: float) -> None:
        """Send a command to the heat pump only if the state has changed."""
        if (
            action == self._last_sent_action
            and temperature == self._last_sent_temperature
        ):
            return  # Nothing to do

        heat_pump_state = self.hass.states.get(self.heat_pump_entity_id)
        if not heat_pump_state:
            _LOGGER.error("Heat pump entity %s not found", self.heat_pump_entity_id)
            return

        if action == "on":
            _LOGGER.info(
                "Smart Climate: heating ON → %s°C (was %s / %s°C)",
                temperature,
                self._last_sent_action,
                self._last_sent_temperature,
            )
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {
                    "entity_id": self.heat_pump_entity_id,
                    "temperature": temperature,
                    "hvac_mode": "heat",
                },
                blocking=True,
            )
        else:
            _LOGGER.info("Smart Climate: heating OFF")
            await self.hass.services.async_call(
                "climate",
                SERVICE_TURN_OFF,
                {"entity_id": self.heat_pump_entity_id},
                blocking=True,
            )

        self._last_sent_action = action
        self._last_sent_temperature = temperature

    async def _send_off(self) -> None:
        """Unconditionally turn the heat pump off (used on disable / unload)."""
        heat_pump_state = self.hass.states.get(self.heat_pump_entity_id)
        if heat_pump_state and heat_pump_state.state != "off":
            _LOGGER.info("Smart Climate: releasing control, turning heat pump off")
            await self.hass.services.async_call(
                "climate",
                SERVICE_TURN_OFF,
                {"entity_id": self.heat_pump_entity_id},
                blocking=False,
            )
        self._last_sent_action = "off"
        self._last_sent_temperature = None
        self.current_action = "off"

    # ------------------------------------------------------------------
    # Data builder
    # ------------------------------------------------------------------

    def _build_debug(
        self,
        action: str,
        target: float,
        room: Optional[float],
        mode: str,
        reason: str,
    ) -> str:
        """Build a concise human-readable status string."""
        room_str = f"{room:.1f}°C" if room is not None else "N/A"
        mode_str = mode.replace("_", " ").title()
        if action == "on":
            return f"ON | {mode_str} → {target}°C | Room: {room_str} | {reason}"
        return f"OFF | {mode_str} → {target}°C | Room: {room_str} | {reason}"

    def _build_data(
        self,
        action: str,
        target_temp: float,
        active_mode: str,
        debug_text: str,
        room_temp: Optional[float],
        schedule_mode: str,
    ) -> dict:
        """Return the full state dict that all entities read from."""
        return {
            "action": action,
            "target_temp": target_temp,
            "active_mode": active_mode,
            "debug_text": debug_text,
            "room_temp": room_temp,
            "schedule_mode": schedule_mode,
            "force_mode": self.force_mode,
            "smart_control_enabled": self.smart_control_enabled,
            "comfort_temp": self.comfort_temp,
            "eco_temp": self.eco_temp,
            "boost_temp": self.boost_temp,
            "deadband_below": self.deadband_below,
            "deadband_above": self.deadband_above,
        }

    # ------------------------------------------------------------------
    # Public API called by switches and number entities
    # ------------------------------------------------------------------

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable or disable smart control and trigger an immediate refresh."""
        _LOGGER.info("Smart Climate: smart control %s", "enabled" if enabled else "disabled")
        self.smart_control_enabled = enabled
        if not enabled:
            await self._send_off()
        await self._async_save()
        await self.async_refresh()

    async def async_set_force_mode(self, mode: Optional[str]) -> None:
        """Set force mode ('comfort', 'eco', 'boost') or clear it (None).

        Force modes are mutually exclusive — setting one clears the others.
        """
        _LOGGER.info("Smart Climate: force mode → %s", mode)
        self.force_mode = mode
        await self._async_save()
        await self.async_refresh()

    async def async_set_temperature(self, temp_type: str, value: float) -> None:
        """Update a temperature setpoint and trigger an immediate refresh."""
        _LOGGER.info("Smart Climate: %s temp → %s°C", temp_type, value)
        if temp_type == "comfort":
            self.comfort_temp = value
        elif temp_type == "eco":
            self.eco_temp = value
        elif temp_type == "boost":
            self.boost_temp = value
        await self._async_save()
        await self.async_refresh()
