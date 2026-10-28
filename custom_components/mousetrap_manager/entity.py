"""Shared entity behavior."""

from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN, SIGNAL_UPDATED


class TrapEntity(Entity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(self, manager, trap_id=None):
        self.manager = manager
        self.trap_id = trap_id

    @property
    def device_info(self):
        if self.trap_id is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self.manager.entry.entry_id)},
                name="Mousetrap Manager",
                manufacturer="Mousetrap Manager",
                model="Felleregister",
            )
        trap = self.manager.ledger.summary(self.trap_id)
        return DeviceInfo(
            identifiers={(DOMAIN, self.trap_id)},
            name=trap["name"],
            manufacturer="Mousetrap Manager",
            model="Vibrasjonsfelle",
        )

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, SIGNAL_UPDATED, self.async_write_ha_state))
