"""Pending checks are available to other Home Assistant automations."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import TrapEntity


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PendingCheck(manager, config["id"]) for config in manager.traps)


class PendingCheck(TrapEntity, BinarySensorEntity):
    _attr_name = "Må kontrolleres"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, manager, trap_id):
        super().__init__(manager, trap_id)
        self._attr_unique_id = f"{DOMAIN}_{trap_id}_pending"

    @property
    def is_on(self):
        trap = self.manager.ledger.summary(self.trap_id)
        return bool(trap["pending_event_id"]) and not trap["archived"]
