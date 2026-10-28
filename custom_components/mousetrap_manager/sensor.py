"""Numeric counters and dashboard state, created automatically."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass

from .const import DOMAIN
from .entity import TrapEntity


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    entities = [CatchCount(manager)]
    for config in manager.traps:
        entities.extend([CatchCount(manager, config["id"]), TrapStatus(manager, config)])
    async_add_entities(entities)


class CatchCount(TrapEntity, SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:rodent"
    _attr_suggested_display_precision = 0

    def __init__(self, manager, trap_id=None):
        super().__init__(manager, trap_id)
        self._attr_unique_id = f"{DOMAIN}_{trap_id or manager.entry.entry_id}_catch_count"
        self._attr_name = "Bekreftede fangster" if trap_id else "Samlet fangst"

    @property
    def native_value(self):
        return len(self.manager.ledger.catches(self.trap_id))

    @property
    def extra_state_attributes(self):
        return {"mousetrap_manager_total": True} if self.trap_id is None else None


class TrapStatus(TrapEntity, SensorEntity):
    _attr_icon = "mdi:mouse-variant"
    _attr_name = "Status"

    def __init__(self, manager, config):
        super().__init__(manager, config["id"])
        self.config = config
        self._attr_unique_id = f"{DOMAIN}_{self.trap_id}_status"

    @property
    def native_value(self):
        trap = self.manager.ledger.summary(self.trap_id)
        return "archived" if trap["archived"] else "pending" if trap["pending_event_id"] else "monitoring"

    @property
    def extra_state_attributes(self):
        trap = self.manager.ledger.summary(self.trap_id)
        return {
            "mousetrap_manager": True,
            "trap_id": self.trap_id,
            "source_device_id": self.config.get("device_id"),
            "trap_name": trap["name"],
            "pending_event_id": trap["pending_event_id"],
            "catch_count": trap["catch_count"],
            "last_catch": trap["last_catch"],
            "last_movement": trap["last_movement"],
            "cooldown_until": trap["cooldown_until"],
            "revision": self.manager.ledger.data["revision"],
        }
