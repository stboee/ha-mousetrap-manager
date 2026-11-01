"""Pending checks are available to other Home Assistant automations."""

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity

from .const import DOMAIN
from .entity import TrapEntity


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        entity
        for config in manager.traps
        for entity in ([PendingCheck(manager, config["id"])] if config.get("type", "snap") == "snap" else [])
        + [InspectionDue(manager, config["id"])]
    )


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


class InspectionDue(TrapEntity, BinarySensorEntity):
    _attr_name = "Inspeksjon nødvendig"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:clipboard-alert-outline"

    def __init__(self, manager, trap_id):
        super().__init__(manager, trap_id)
        self._attr_unique_id = f"{DOMAIN}_{trap_id}_inspection_due"

    @property
    def is_on(self):
        return self.manager.summary(self.trap_id)["inspection_due"]
