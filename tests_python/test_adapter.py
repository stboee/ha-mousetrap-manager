"""Run the adapter against the actual Home Assistant 2026.10.4 classes."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import HomeAssistant

from custom_components.mousetrap_manager.binary_sensor import PendingCheck
from custom_components.mousetrap_manager.config_flow import MousetrapOptionsFlow, valid_topic
from custom_components.mousetrap_manager.manager import TrapManager
from custom_components.mousetrap_manager.sensor import CatchCount, TrapStatus


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    yield instance
    await instance.async_stop()


@pytest.fixture
def entry():
    return SimpleNamespace(
        entry_id="test",
        options={"traps": [{"id": "a", "name": "Loft", "device_id": "device", "topic": "zigbee2mqtt/Vibrasjon"}]},
    )


async def start(hass, entry):
    manager = TrapManager(hass, entry)
    manager._store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ):
        await manager.async_start()
    return manager


async def test_concurrent_confirmation_counts_once_and_is_durable(hass, entry):
    manager = await start(hass, entry)
    await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
    pending = manager.ledger.summary("a")["pending_event_id"]
    results = await asyncio.gather(*[manager.async_acknowledge("a", pending, True) for _ in range(10)])
    assert sum(results) == 1
    assert CatchCount(manager).native_value == 1
    persisted = manager._store.async_save.call_args.args[0]
    restored = TrapManager(hass, entry)
    restored._store = SimpleNamespace(async_load=AsyncMock(return_value=persisted), async_save=AsyncMock())
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ):
        await restored.async_start()
    assert CatchCount(restored).native_value == 1
    assert not await restored.async_acknowledge("a", pending, True)
    assert CatchCount(restored)._attr_state_class == SensorStateClass.TOTAL


async def test_save_failure_does_not_publish_an_uncommitted_capture(hass, entry):
    manager = await start(hass, entry)
    await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
    pending = manager.ledger.summary("a")["pending_event_id"]
    manager._store.async_save.side_effect = OSError("disk full")
    with pytest.raises(OSError):
        await manager.async_acknowledge("a", pending, True)
    assert len(manager.ledger.catches()) == 0
    assert manager.ledger.summary("a")["pending_event_id"] == pending
    manager._store.async_save.side_effect = None
    assert await manager.async_acknowledge("a", pending, True)
    assert len(manager.ledger.catches()) == 1


async def test_notifications_default_off_and_optional_notice_has_stable_id(hass, entry):
    with patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create:
        manager = await start(hass, entry)
        await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
        create.assert_not_called()
        entry.options["notifications_enabled"] = True
        manager._sync_notifications()
        assert create.call_args.kwargs["notification_id"] == "mousetrap_manager_a"
        pending = manager.ledger.summary("a")["pending_event_id"]
        with patch("custom_components.mousetrap_manager.manager.persistent_notification.async_dismiss") as dismiss:
            await manager.async_acknowledge("a", pending, False)
            dismiss.assert_called_with(hass, "mousetrap_manager_a")


async def test_mqtt_ignores_replays_other_actions_and_bad_payloads(hass, entry):
    manager = TrapManager(hass, entry)
    manager._store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ) as subscribe:
        await manager.async_start()
        callback = subscribe.call_args.args[2]
        for payload, retained in [
            ("{bad", False),
            ("[]", False),
            ('{"action":"triple_strike"}', False),
            ('{"action":"movement"}', True),
            ('{"battery":90}', False),
        ]:
            await callback(SimpleNamespace(payload=payload, retain=retained))
        assert not PendingCheck(manager, "a").is_on
        await callback(SimpleNamespace(payload='{"action":"movement"}', retain=False))
        assert PendingCheck(manager, "a").is_on
        assert CatchCount(manager).native_value == 0
        await callback(SimpleNamespace(payload='{"action":"movement"}', retain=False))
        assert len([e for e in manager.ledger.data["events"] if e["type"] == "movement"]) == 1
        manager.async_stop()


async def test_real_store_survives_a_new_manager(hass, entry):
    manager = TrapManager(hass, entry)
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ):
        await manager.async_start()
        await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
        pending = manager.ledger.summary("a")["pending_event_id"]
        await manager.async_acknowledge("a", pending, True)
        manager.async_stop()
        replacement = TrapManager(hass, entry)
        await replacement.async_start()
        assert CatchCount(replacement).native_value == 1
        assert not PendingCheck(replacement, "a").is_on
        assert TrapStatus(replacement, entry.options["traps"][0]).extra_state_attributes["last_catch"]
        replacement.async_stop()


async def test_admin_undo_form_pins_the_capture_and_requires_confirmation(hass, entry):
    manager = await start(hass, entry)
    await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
    await manager.async_acknowledge("a", manager.ledger.summary("a")["pending_event_id"], True)
    hass.data["mousetrap_manager"] = {"test": manager}
    hass.config_entries = SimpleNamespace(async_get_known_entry=lambda entry_id: entry)
    flow = MousetrapOptionsFlow()
    flow.hass = hass
    flow.handler = "test"
    flow.flow_id = "test-flow"
    form = await flow.async_step_undo({"trap_id": "a"})
    assert form["step_id"] == "undo_confirm"
    rejected = await flow.async_step_undo_confirm({"confirm": False})
    assert rejected["errors"]["confirm"] == "confirmation_required"
    result = await flow.async_step_undo_confirm({"confirm": True})
    assert result["reason"] == "capture_undone"
    assert CatchCount(manager).native_value == 0


async def test_shutdown_waits_for_an_inflight_durable_transaction(hass, entry):
    manager = await start(hass, entry)
    writing = asyncio.Event()
    finish = asyncio.Event()

    async def slow_save(data):
        writing.set()
        await finish.wait()

    manager._store.async_save.side_effect = slow_save
    change = asyncio.create_task(manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00")))
    await writing.wait()
    shutdown = asyncio.create_task(manager.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    finish.set()
    await change
    await shutdown
    assert manager.ledger.summary("a")["pending_event_id"]


@pytest.mark.parametrize(
    "topic, valid",
    [("zigbee2mqtt/Vibrasjon", True), ("zigbee2mqtt/#", False), ("+", False), ("", False), (" bad", False)],
)
def test_subscriptions_require_an_exact_topic(topic, valid):
    assert valid_topic(topic) == valid
