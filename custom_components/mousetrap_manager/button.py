"""Maintenance is also available from each trap's device page."""

from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import TrapEntity
from .ledger import LedgerError


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        MaintenanceButton(manager, config["id"], action)
        for config in manager.traps
        for action in ("bait_replaced", "inspection_completed")
    )


class MaintenanceButton(TrapEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager, trap_id, action):
        super().__init__(manager, trap_id)
        self.action = action
        self._attr_unique_id = f"{DOMAIN}_{trap_id}_{action}"
        self._attr_name = "Åte byttet" if action == "bait_replaced" else "Inspeksjon utført"
        self._attr_icon = "mdi:cheese" if action == "bait_replaced" else "mdi:clipboard-check-outline"

    @property
    def available(self):
        trap = self.manager.ledger.summary(self.trap_id)
        return not trap["archived"] and (self.action == "bait_replaced" or not trap["pending_event_id"])

    async def async_press(self):
        try:
            await self.manager.async_maintenance(self.trap_id, self.action)
        except LedgerError as err:
            raise HomeAssistantError(str(err)) from err
