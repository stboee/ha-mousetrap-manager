"""Mousetrap Manager: one persistent register for all configured traps."""

from pathlib import Path

import probatio as vol
from homeassistant.components import websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import CARD_URL, DOMAIN, PLATFORMS
from .ledger import LedgerError
from .manager import TrapManager


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARD_URL, str(Path(__file__).parent / "frontend" / "mousetrap-manager-card.js"), False)]
    )

    async def acknowledge(call: ServiceCall):
        for manager in hass.data[DOMAIN].values():
            if call.data["trap_id"] in manager.ledger.data["traps"]:
                try:
                    await manager.async_acknowledge(
                        call.data["trap_id"], call.data["event_id"], call.service == "confirm_catch"
                    )
                except LedgerError as err:
                    raise HomeAssistantError(str(err)) from err
                return
        raise HomeAssistantError("Unknown trap")

    schema = vol.Schema({vol.Required("trap_id"): cv.string, vol.Required("event_id"): cv.string})
    for service in ("confirm_catch", "false_alarm"):
        hass.services.async_register(DOMAIN, service, acknowledge, schema=schema)
    websocket_api.async_register_command(hass, websocket_journal)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    manager = TrapManager(hass, entry)
    await manager.async_start()
    hass.data[DOMAIN][entry.entry_id] = manager
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        manager.async_stop()
        hass.data[DOMAIN].pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    manager = hass.data[DOMAIN][entry.entry_id]
    await manager.async_shutdown()
    hass.data[DOMAIN].pop(entry.entry_id)
    return True


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_reload(entry.entry_id)


@websocket_api.websocket_command(
    {
        "type": f"{DOMAIN}/journal",
        vol.Optional("trap_id"): str,
        vol.Optional("before"): str,
        vol.Optional("limit", default=50): vol.All(int, vol.Range(min=1, max=200)),
    }
)
@callback
def websocket_journal(hass, connection, msg):
    """Paginated, authenticated history; never store the growing journal in entity attributes."""
    managers = list(hass.data[DOMAIN].values())
    if not managers:
        connection.send_error(msg["id"], "not_loaded", "Mousetrap Manager is not loaded")
        return
    try:
        events = managers[0].ledger.journal(msg.get("trap_id"), msg.get("before"), msg["limit"])
    except LedgerError as err:
        connection.send_error(msg["id"], "invalid_cursor", str(err))
        return
    connection.send_result(
        msg["id"], {"events": events, "next_cursor": events[-1]["id"] if len(events) == msg["limit"] else None}
    )
