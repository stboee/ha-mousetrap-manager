"""Persistence, subscriptions and shared updates for all traps."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components import mqtt, persistent_notification
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULT_COOLDOWN, DOMAIN, SIGNAL_UPDATED, STORAGE_VERSION
from .ledger import Ledger, LedgerError, instant
from .presentation import display_settings, presentation, source_entities
from .victor_recovery import VictorRecovery

_LOGGER = logging.getLogger(__name__)


def sensor_timestamp(value, now):
    """Read Zigbee2MQTT last_seen. MQTT delivery alone is not sensor contact."""
    try:
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, (int, float)) or (isinstance(value, str) and value.replace(".", "", 1).isdigit()):
            epoch = float(value)
            result = datetime.fromtimestamp(epoch / 1000 if epoch > 1e11 else epoch, timezone.utc)
        else:
            result = instant(value)
        if result > now + timedelta(minutes=5):
            return None
        return result.astimezone(timezone.utc).isoformat()
    except ValueError, TypeError, OverflowError, OSError:
        return None


class TrapManager:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.ledger = Ledger()
        self._store = Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")
        self._lock = asyncio.Lock()
        self._unsubscribers = []
        self._notified = {}
        self._stopping = False
        self.victor_recovery = VictorRecovery(hass, entry)

    @property
    def traps(self):
        return self.entry.options.get("traps", [])

    @property
    def notifications_enabled(self):
        return self.entry.options.get("notifications_enabled", False)

    async def async_start(self):
        saved = await self._store.async_load()
        self.ledger = Ledger(saved)
        await self._change(lambda ledger: ledger.sync_traps(self.traps, dt_util.utcnow().isoformat()))
        try:
            for trap in self.traps:
                if trap.get("archived") or trap.get("type", "snap") != "snap":
                    continue

                async def message_received(message, trap_id=trap["id"]):
                    try:
                        payload = json.loads(message.payload)
                    except ValueError, TypeError:
                        return
                    if not isinstance(payload, dict):
                        return
                    now = dt_util.utcnow()
                    contact = sensor_timestamp(payload.get("last_seen"), now)

                    def apply(ledger):
                        changed = ledger.sensor_contact(trap_id, contact) if contact else False
                        # Retained telemetry can restore its real timestamp, never replay an action.
                        if not message.retain and payload.get("action") == "movement":
                            changed = ledger.movement(trap_id, now.isoformat()) or changed
                        return changed

                    try:
                        await self._change(apply)
                    except Exception:
                        _LOGGER.exception("Could not persist sensor report for trap %s", trap_id)

                unsub = await mqtt.async_subscribe(self.hass, trap["topic"], message_received, qos=1)
                self._unsubscribers.append(unsub)
            self._unsubscribers.append(async_track_time_interval(self.hass, self._tick, timedelta(minutes=1)))
            self._unsubscribers.append(self.hass.bus.async_listen(EVENT_STATE_CHANGED, self._source_changed))
            for event in ("entity_registry_updated", "device_registry_updated", "area_registry_updated"):
                self._unsubscribers.append(self.hass.bus.async_listen(event, self._registry_changed))
        except Exception:
            self.async_stop()
            raise
        self._sync_notifications()
        await self.victor_recovery.async_start()

    def async_stop(self):
        self._stopping = True
        self.victor_recovery.stop()
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    async def async_shutdown(self):
        self.async_stop()
        # Finish the last durable transaction before another manager reads the same Store on reload.
        async with self._lock:
            pass
        await self.victor_recovery.async_shutdown()

    async def _change(self, operation):
        async with self._lock:
            if self._stopping:
                raise LedgerError("Integrasjonen lastes på nytt. Prøv igjen.")
            next_ledger = self.ledger.clone()
            changed = operation(next_ledger)
            if not changed:
                return False
            # Publish only after a successful atomic Store write. A failed write leaves the old state intact.
            await self._store.async_save(next_ledger.data)
            self.ledger = next_ledger
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)
            self._sync_notifications()
            return True

    async def async_acknowledge(self, trap_id, event_id, caught):
        config = next((t for t in self.traps if t["id"] == trap_id), {})
        if config.get("type", "snap") != "snap":
            raise LedgerError("Victor-fangst håndteres av Victor-integrasjonen")
        return await self._change(
            lambda ledger: ledger.acknowledge(
                trap_id,
                event_id,
                caught,
                dt_util.utcnow().isoformat(),
                self.entry.options.get("cooldown_seconds", DEFAULT_COOLDOWN),
            )
        )

    async def async_undo(self, trap_id, capture_id):
        return await self._change(lambda ledger: ledger.undo(trap_id, capture_id, dt_util.utcnow().isoformat()))

    async def async_maintenance(self, trap_id, action, event_id=None):
        trap = self.ledger.summary(trap_id)
        field = "bait_event_id" if action == "bait_replaced" else "inspection_event_id"
        token = event_id if event_id is not None else trap[field] or "initial"
        now = dt_util.utcnow().isoformat()
        if action == "bait_replaced":
            return await self._change(lambda ledger: ledger.replace_bait(trap_id, token, now))
        if action != "inspection_completed":
            raise LedgerError("Unknown maintenance action")
        return await self._change(
            lambda ledger: ledger.inspect(
                trap_id, token, now, self.entry.options.get("cooldown_seconds", DEFAULT_COOLDOWN)
            )
        )

    def summary(self, trap_id, now=None):
        config = next((t for t in self.traps if t["id"] == trap_id), {})
        now = now or dt_util.utcnow()
        summary = {
            **self.ledger.maintenance(trap_id, now.isoformat(), int(config.get("inspection_interval_days", 0))),
            "show_bait_age": config.get("show_bait_age", True),
            "inspection_interval_days": int(config.get("inspection_interval_days", 0)),
        }
        summary["presentation"] = presentation(self, config, summary, now)
        return summary

    @property
    def display(self):
        return display_settings(self.entry.options)

    @callback
    def _source_changed(self, event):
        if self._stopping:
            return
        entity_id = event.data.get("entity_id")
        if any(entity_id in source_entities(self.hass, t).values() for t in self.traps if not t.get("archived")):
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)
            self._sync_notifications()

    @callback
    def _registry_changed(self, event):
        if not self._stopping:
            async_dispatcher_send(self.hass, SIGNAL_UPDATED)

    @callback
    def _tick(self, now):
        """Deadlines and ages advance even while every dashboard is closed."""
        if self._stopping:
            return
        async_dispatcher_send(self.hass, SIGNAL_UPDATED)
        self._sync_notifications()
        self.victor_recovery.async_request_check()

    def _sync_notifications(self):
        for trap_id, trap in self.ledger.data["traps"].items():
            notification_id = f"{DOMAIN}_{trap_id}"
            movement_enabled = self.notifications_enabled and self.entry.options.get(
                "movement_notifications_enabled", True
            )
            if movement_enabled and trap["pending_event_id"] and not trap["archived"]:
                if self._notified.get(trap_id) != trap["pending_event_id"]:
                    persistent_notification.async_create(
                        self.hass,
                        f"Bevegelse er registrert ved **{trap['name']}**. Kontroller og klargjør fellen, og kvitter i musefellekortet.",
                        title="Musefelle må kontrolleres",
                        notification_id=notification_id,
                    )
                    self._notified[trap_id] = trap["pending_event_id"]
            else:
                persistent_notification.async_dismiss(self.hass, notification_id)
                self._notified.pop(trap_id, None)
            config = next((t for t in self.traps if t["id"] == trap_id), {})
            summary = self.summary(trap_id)
            key = f"inspection_{trap_id}"
            notice = f"{DOMAIN}_inspection_{trap_id}"
            if (
                self.notifications_enabled
                and config.get("inspection_notifications_enabled", False)
                and summary["inspection_due"]
            ):
                deadline = summary["next_inspection"] or "unknown"
                if self._notified.get(key) != deadline:
                    persistent_notification.async_create(
                        self.hass,
                        f"**{trap['name']}** har nådd fristen for inspeksjon. Kontroller fellen og åtet, og kvitter i musefellekortet.",
                        title="Tid for inspeksjon av musefelle",
                        notification_id=notice,
                    )
                    self._notified[key] = deadline
            else:
                persistent_notification.async_dismiss(self.hass, notice)
                self._notified.pop(key, None)
            health_notice = f"{DOMAIN}_health_{trap_id}"
            warnings = summary["presentation"]["warnings"]
            if (
                self.notifications_enabled
                and self.entry.options.get("health_notifications_enabled", False)
                and warnings
                and not trap["archived"]
            ):
                message = " · ".join(warnings)
                if self._notified.get(health_notice) != message:
                    persistent_notification.async_create(
                        self.hass,
                        f"**{trap['name']}**: {message}.",
                        title="Musefelle: sensorkontakt eller batteri",
                        notification_id=health_notice,
                    )
                    self._notified[health_notice] = message
            else:
                persistent_notification.async_dismiss(self.hass, health_notice)
                self._notified.pop(health_notice, None)
