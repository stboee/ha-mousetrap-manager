"""Opt-in recovery of an existing Victor entry, without a second Victor client."""

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import EVENT_STATE_CHANGED, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import CoreState, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DOMAIN, SIGNAL_UPDATED

_LOGGER = logging.getLogger(__name__)

RECOVERY_DEFAULTS = {
    "victor_recovery_enabled": False,
    "victor_unavailable_minutes": 20,
    "victor_reload_cooldown_minutes": 60,
    "victor_reload_max_attempts": 3,
}
RECOVERY_STATES = [
    "disabled",
    "starting",
    "monitoring",
    "waiting",
    "cooldown",
    "reloading",
    "limit_reached",
    "auth_required",
    "setup_retry",
    "not_loaded",
    "not_found",
    "storage_error",
]


class VictorRecovery:
    def __init__(self, hass, entry):
        self.hass = hass
        self.options = {**RECOVERY_DEFAULTS, **entry.options}
        self.target_id = self.options.get("victor_entry_id")
        self.status = "disabled"
        self.data = {"entry_id": self.target_id, "attempts": 0, "last_attempt": None, "last_result": None}
        self._store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.victor_recovery")
        self._unavailable_since = None
        self._watched = set()
        self._healthy_seen = False
        self._stopped = False
        self._storage_failed = False
        self._unsubscribe = None
        self._task = None
        self._lock = asyncio.Lock()

    @property
    def enabled(self):
        return self.options["victor_recovery_enabled"]

    @property
    def attributes(self):
        return {
            **self.data,
            "unavailable_since": self._unavailable_since.isoformat() if self._unavailable_since else None,
            **{key: self.options[key] for key in RECOVERY_DEFAULTS},
        }

    @callback
    def _publish(self, status):
        self.status = status
        if not self._stopped:
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    async def async_start(self):
        if not self.enabled:
            return
        try:
            saved = await self._store.async_load()
            if saved and saved.get("entry_id") == self.target_id:
                if not isinstance(saved.get("attempts"), int) or saved["attempts"] < 0:
                    raise ValueError("Invalid Victor recovery attempt count")
                if saved.get("last_attempt"):
                    parsed = dt_util.parse_datetime(saved["last_attempt"])
                    if parsed is None or parsed.tzinfo is None:
                        raise ValueError("Invalid Victor recovery timestamp")
                self.data = saved
            token = self.options.get("victor_recovery_reset_token")
            if self.data.get("reset_token") != token:
                self.data = {**self.data, "attempts": 0, "reset_token": token}
                if not await self._save():
                    return
        except Exception:
            self._storage_failed = True
            self._publish("storage_error")
            _LOGGER.exception("Victor recovery is paused because its saved state could not be read")
            return
        self._unsubscribe = self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._state_changed)
        self._publish("starting")
        self.async_request_check()

    @callback
    def stop(self):
        self._stopped = True
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    async def async_shutdown(self):
        self.stop()
        # Do not cancel an external integration halfway through its unload/setup.
        if self._task and self._task is not asyncio.current_task():
            await asyncio.shield(self._task)

    @callback
    def _state_changed(self, event):
        if event.data["entity_id"] not in self._watched:
            return
        state = event.data.get("new_state")
        if state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) and not state.attributes.get("restored"):
            self._unavailable_since = None
            self._healthy_seen = True
        self.async_request_check()

    @callback
    def async_request_check(self):
        if not self.enabled or self._stopped or self._storage_failed or (self._task and not self._task.done()):
            return
        self._task = self.hass.async_create_task(self.async_check(), "Mousetrap Manager Victor recovery")

    async def _save(self):
        try:
            await self._store.async_save(self.data)
            return True
        except Exception:
            self._storage_failed = True
            self._publish("storage_error")
            _LOGGER.exception("Victor recovery is paused because its attempt state could not be saved")
            return False

    async def async_check(self):
        if self._stopped or not self.enabled or self._storage_failed or self._lock.locked():
            return
        async with self._lock:
            await self._check()

    def _blocked_status(self, target):
        if (
            target is None
            or target.domain != "victorsmartkill"
            or self.hass.config_entries.async_get_entry(self.target_id) is not target
        ):
            return "not_found"
        if any(target.async_get_active_flows(self.hass, {SOURCE_REAUTH})):
            return "auth_required"
        if target.disabled_by or target.state not in (ConfigEntryState.LOADED, ConfigEntryState.SETUP_ERROR):
            return "setup_retry" if target.state is ConfigEntryState.SETUP_RETRY else "not_loaded"
        return None

    @staticmethod
    def _failure_observed(target, states):
        return target is not None and (
            target.state is ConfigEntryState.SETUP_ERROR
            or target.state is ConfigEntryState.LOADED
            and bool(states)
            and all(
                state and state.state == STATE_UNAVAILABLE and not state.attributes.get("restored") for state in states
            )
        )

    async def _check(self):
        if self.hass.state is not CoreState.running:
            self._unavailable_since = None
            self._publish("starting")
            return
        target = self.hass.config_entries.async_get_entry(self.target_id) if self.target_id else None
        # async_reload aborts reauth flows, so this check must precede every attempt.
        if blocked := self._blocked_status(target):
            self._unavailable_since = None
            self._publish(blocked)
            return
        registry = er.async_get(self.hass)
        self._watched = {
            entity.entity_id
            for entity in er.async_entries_for_config_entry(registry, self.target_id)
            if not entity.disabled_by
        }
        states = [self.hass.states.get(entity_id) for entity_id in self._watched]
        healthy = target.state is ConfigEntryState.LOADED and any(
            state and state.state not in (STATE_UNAVAILABLE, STATE_UNKNOWN) and not state.attributes.get("restored")
            for state in states
        )
        if healthy or self._healthy_seen:
            self._healthy_seen = False
            self._unavailable_since = None
            if self.data["attempts"]:
                self.data = {**self.data, "attempts": 0}
                if not await self._save():
                    return
            if healthy:
                self._publish("monitoring")
                return
        unavailable = self._failure_observed(target, states)
        if not unavailable:
            self._unavailable_since = None
            self._publish("starting")
            return
        now = dt_util.utcnow()
        if self._unavailable_since is None:
            self._unavailable_since = now
        if self.data["attempts"] >= self.options["victor_reload_max_attempts"]:
            self._publish("limit_reached")
            return
        if now - self._unavailable_since < timedelta(minutes=self.options["victor_unavailable_minutes"]):
            self._publish("waiting")
            return
        last_attempt = dt_util.parse_datetime(self.data["last_attempt"]) if self.data["last_attempt"] else None
        if last_attempt and now - last_attempt < timedelta(minutes=self.options["victor_reload_cooldown_minutes"]):
            self._publish("cooldown")
            return
        # Reserve and persist an attempt before doing anything to Victor.
        before_attempt = self.data
        self.data = {
            **self.data,
            "attempts": self.data["attempts"] + 1,
            "last_attempt": now.isoformat(),
            "last_result": "started",
        }
        if not await self._save():
            return
        # Saving yields to HA: the user may have disabled the option, started
        # reauthentication or manually reloaded Victor in the meantime.
        blocked = self._blocked_status(target)
        current = [self.hass.states.get(entity_id) for entity_id in self._watched]
        still_unavailable = self._failure_observed(target, current)
        if self._stopped or self.hass.state is not CoreState.running or blocked or not still_unavailable:
            self.data = before_attempt
            self._unavailable_since = None
            if await self._save():
                self._publish(blocked or "starting")
            return
        self._publish("reloading")
        _LOGGER.info(
            "Reloading Victor entry %s after sustained unavailability (attempt %s/%s)",
            self.target_id,
            self.data["attempts"],
            self.options["victor_reload_max_attempts"],
        )
        try:
            success = await self.hass.config_entries.async_reload(self.target_id)
            result = "completed" if success else "failed"
            if not success:
                _LOGGER.warning("Automatic reload of Victor entry %s did not complete successfully", self.target_id)
        except Exception:
            result = "error"
            _LOGGER.exception("Automatic reload of Victor entry %s failed", self.target_id)
        self.data = {**self.data, "last_result": result}
        current = [self.hass.states.get(entity_id) for entity_id in self._watched]
        latest = self.hass.config_entries.async_get_entry(self.target_id)
        self._unavailable_since = dt_util.utcnow() if self._failure_observed(latest, current) else None
        if await self._save():
            self._publish("cooldown")
