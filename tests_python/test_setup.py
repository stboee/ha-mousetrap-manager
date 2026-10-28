"""Exercise config forms and actual Home Assistant service registration."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.mousetrap_manager import async_setup
from custom_components.mousetrap_manager.config_flow import MousetrapOptionsFlow
from custom_components.mousetrap_manager.manager import TrapManager
from custom_components.mousetrap_manager.sensor import CatchCount


@pytest.fixture
async def env(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    entry = SimpleNamespace(
        entry_id="test",
        options={"traps": [{"id": "a", "name": "Loft", "device_id": "device-a", "topic": "zigbee2mqtt/a"}]},
    )
    hass.config_entries = SimpleNamespace(async_get_known_entry=lambda _: entry)
    flow = MousetrapOptionsFlow()
    flow.hass = hass
    flow.handler = "test"
    flow.flow_id = "test-flow"
    yield hass, entry, flow
    await hass.async_stop()


async def test_add_trap_form_creates_identity_and_keeps_existing_traps(env):
    hass, entry, flow = env
    with patch(
        "custom_components.mousetrap_manager.config_flow.dr.async_get",
        return_value=SimpleNamespace(async_get=lambda _: SimpleNamespace()),
    ):
        result = await flow.async_step_add_trap({"name": "Garasje", "device_id": "device-b", "topic": "zigbee2mqtt/b"})
    assert result["type"] == "create_entry"
    traps = result["data"]["traps"]
    assert traps[0]["id"] == "a"
    assert len(traps[1]["id"]) == 32
    assert len(entry.options["traps"]) == 1
    assert result["data"]["notifications_enabled"] is False


async def test_duplicate_sensor_or_topic_is_rejected(env):
    hass, entry, flow = env
    with patch(
        "custom_components.mousetrap_manager.config_flow.dr.async_get",
        return_value=SimpleNamespace(async_get=lambda _: SimpleNamespace()),
    ):
        for device, topic in [("device-a", "zigbee2mqtt/b"), ("device-b", "zigbee2mqtt/a")]:
            result = await flow.async_step_add_trap({"name": "Other", "device_id": device, "topic": topic})
            assert result["errors"]["base"] == "already_registered"


async def test_archiving_and_renaming_keeps_trap_id(env):
    hass, entry, flow = env
    flow._editing = "a"
    with patch(
        "custom_components.mousetrap_manager.config_flow.dr.async_get",
        return_value=SimpleNamespace(async_get=lambda _: SimpleNamespace()),
    ):
        result = await flow.async_step_edit_details(
            {"name": "Nytt navn", "device_id": "device-a", "topic": "zigbee2mqtt/renamed", "archived": True}
        )
    assert result["data"]["traps"] == [
        {"id": "a", "name": "Nytt navn", "device_id": "device-a", "topic": "zigbee2mqtt/renamed", "archived": True}
    ]


async def test_real_ha_services_use_pinned_episode_and_do_not_offer_undo(env):
    hass, entry, flow = env
    hass.http = SimpleNamespace(async_register_static_paths=AsyncMock())
    with patch("custom_components.mousetrap_manager.websocket_api.async_register_command"):
        await async_setup(hass, {})
    manager = TrapManager(hass, entry)
    manager._store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ):
        await manager.async_start()
    hass.data["mousetrap_manager"]["test"] = manager
    await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
    data = {"trap_id": "a", "event_id": manager.ledger.summary("a")["pending_event_id"]}
    for _ in range(2):
        await hass.services.async_call("mousetrap_manager", "confirm_catch", data, blocking=True)
    assert CatchCount(manager).native_value == 1
    assert not hass.services.has_service("mousetrap_manager", "undo")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("mousetrap_manager", "false_alarm", data, blocking=True)
    assert (
        hass.http.async_register_static_paths.call_args.args[0][0].url_path
        == "/mousetrap_manager/mousetrap-manager-card.js"
    )
    manager.async_stop()
