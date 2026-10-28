"""Persistence, subscriptions and shared updates for all traps."""

import asyncio
import json
import logging

from homeassistant.components import mqtt, persistent_notification
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from .const import DEFAULT_COOLDOWN, DOMAIN, SIGNAL_UPDATED, STORAGE_VERSION
from .ledger import Ledger, LedgerError

_LOGGER = logging.getLogger(__name__)


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
                if trap.get("archived"):
                    continue

                async def message_received(message, trap_id=trap["id"]):
                    # A replayed action is an old event, not a new physical movement.
                    if message.retain:
                        return
                    try:
                        payload = json.loads(message.payload)
                    except ValueError, TypeError:
                        return
                    if not isinstance(payload, dict) or payload.get("action") != "movement":
                        return
                    try:
                        await self._change(lambda ledger: ledger.movement(trap_id, dt_util.utcnow().isoformat()))
                    except Exception:
                        _LOGGER.exception("Could not persist movement for trap %s", trap_id)

                unsub = await mqtt.async_subscribe(self.hass, trap["topic"], message_received, qos=1)
                self._unsubscribers.append(unsub)
        except Exception:
            self.async_stop()
            raise
        self._sync_notifications()

    def async_stop(self):
        self._stopping = True
        for unsubscribe in self._unsubscribers:
            unsubscribe()
        self._unsubscribers.clear()

    async def async_shutdown(self):
        self.async_stop()
        # Finish the last durable transaction before another manager reads the same Store on reload.
        async with self._lock:
            pass

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

    def _sync_notifications(self):
        for trap_id, trap in self.ledger.data["traps"].items():
            notification_id = f"{DOMAIN}_{trap_id}"
            if self.notifications_enabled and trap["pending_event_id"] and not trap["archived"]:
                if self._notified.get(trap_id) == trap["pending_event_id"]:
                    continue
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
