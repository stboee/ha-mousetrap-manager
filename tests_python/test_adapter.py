"""Run the adapter against the actual Home Assistant 2026.10.4 classes."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.mousetrap_manager.binary_sensor import PendingCheck
from custom_components.mousetrap_manager.config_flow import MousetrapOptionsFlow, valid_topic
from custom_components.mousetrap_manager.ledger import LedgerError
from custom_components.mousetrap_manager.manager import TrapManager
from custom_components.mousetrap_manager.notification_preferences import notice_enabled
from custom_components.mousetrap_manager.sensor import CatchCount, MaintenanceSensor, TrapStatus, TrapsInUse


@pytest.fixture
async def hass(tmp_path):
    instance = HomeAssistant(str(tmp_path))
    instance.config_entries = ConfigEntries(instance, {})
    await instance.config_entries.async_initialize()
    dr.async_setup(instance)
    await dr.async_load(instance)
    await er.async_load(instance)
    await ar.async_load(instance)
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


async def test_graphic_changes_are_presentation_only_and_keep_pending_and_history(hass, entry):
    manager = await start(hass, entry)
    await manager._change(lambda ledger: ledger.movement("a", "2026-10-28T10:00:00+00:00"))
    pending = manager.ledger.summary("a")["pending_event_id"]
    await manager.async_acknowledge("a", pending, True)
    await manager.async_maintenance("a", "bait_replaced", "initial")
    next_movement = datetime.fromisoformat(manager.ledger.data["traps"]["a"]["cooldown_until"]) + timedelta(seconds=1)
    await manager._change(lambda ledger: ledger.movement("a", next_movement.isoformat()))
    before = manager.ledger.clone().data
    for graphic, prefix in (
        (None, "snap"),
        ("rapp_2", "snap-rapp-2"),
        ("biltema_giljotin", "snap-biltema-giljotin"),
        ("classic", "snap"),
        ("unknown", "snap"),
    ):
        entry.options["traps"][0]["snap_graphic"] = graphic
        view = manager.summary("a")
        assert view["presentation"]["graphic"] == prefix
        assert view["presentation"]["scene"] == "pending"
        assert view["catch_count"] == 1
        assert view["last_bait_replaced"]
        assert manager.ledger.data == before
    manager.async_stop()


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


async def test_trap_actions_guard_new_events_and_update_operational_counts(hass, entry):
    manager = await start(hass, entry)
    count = TrapsInUse(manager, "snap", "Klappfeller i bruk")
    stamp = manager.ledger.management_stamp("a")
    assert count.native_value == 1
    await manager._change(lambda ledger: ledger.movement("a", "2026-11-26T10:00:00+00:00"))
    with pytest.raises(LedgerError):
        await manager.async_manage_trap("a", stamp, "delete")
    assert manager.ledger.summary("a")["pending_event_id"] and count.native_value == 1
    await manager.async_acknowledge("a", manager.ledger.summary("a")["pending_event_id"], True)

    async def manage(action):
        return await manager.async_manage_trap("a", manager.ledger.management_stamp("a"), action)

    await manage("pause")
    assert count.native_value == 0
    await manage("resume")
    assert count.native_value == 1
    await manage("start_test")
    assert count.native_value == 0 and CatchCount(manager).native_value == 1
    entry.options["notifications_enabled"] = True
    with patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create:
        await manager._change(lambda ledger: ledger.movement("a", "2026-11-26T11:00:00+00:00"))
        assert manager.ledger.summary("a")["pending_event_id"]
        assert manager.attention()["count"] == 0
        create.assert_not_called()
        await manager.async_acknowledge("a", manager.ledger.summary("a")["pending_event_id"], True)
    assert TrapStatus(manager, entry.options["traps"][0]).extra_state_attributes["catch_count"] == 1
    assert CatchCount(manager).native_value == 1
    await manage("reset_test")
    assert manager.ledger.summary("a")["catch_count"] == 0
    await manage("delete")
    assert manager.traps == [] and CatchCount(manager).native_value == 0
    manager.async_stop()


def test_notice_overrides_obey_master_and_keep_legacy_inspection_opt_out():
    options = {"notifications_enabled": True, "inspection_notifications_enabled": True}
    trap = {"inspection_notifications_enabled": False, "notification_overrides": {"movement": "off", "health": "on"}}
    assert not notice_enabled(options, trap, "inspection")
    assert not notice_enabled(options, trap, "movement")
    assert notice_enabled(options, trap, "health")
    assert notice_enabled(options, {}, "inspection")
    assert not notice_enabled({**options, "notifications_enabled": False}, trap, "health")


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
            dismiss.assert_any_call(hass, "mousetrap_manager_a")


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


async def test_sensor_contact_uses_actual_last_seen_not_delivery_or_state_change(hass, entry):
    manager = TrapManager(hass, entry)
    manager._store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ) as subscribe:
        await manager.async_start()
        callback = subscribe.call_args.args[2]
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    with patch("custom_components.mousetrap_manager.manager.dt_util.utcnow", return_value=now):
        await callback(SimpleNamespace(payload='{"action":"movement","last_seen":"2026-11-01T09:00:00Z"}', retain=True))
        assert not PendingCheck(manager, "a").is_on
        assert manager.summary("a")["last_sensor_contact"] == "2026-11-01T09:00:00+00:00"
        for payload in [
            '{"battery":100}',
            '{"last_seen":"invalid"}',
            '{"last_seen":"2026-11-01T09:30:00"}',
            '{"last_seen":"2026-11-02T10:00:00Z"}',
            '{"last_seen":"2026-10-30T10:00:00Z"}',
        ]:
            await callback(SimpleNamespace(payload=payload, retain=False))
        assert manager.summary("a")["last_sensor_contact"] == "2026-11-01T09:00:00+00:00"
        stamp = int(now.timestamp() * 1000)
        await callback(SimpleNamespace(payload=f'{{"last_seen":{stamp},"battery":100}}', retain=False))
        assert MaintenanceSensor(manager, "a", "last_sensor_contact").native_value == now
        assert not PendingCheck(manager, "a").is_on
        assert not [e for e in manager.ledger.data["events"] if e["type"] != "registered"]
    manager.async_stop()


async def test_inspection_deadline_notifies_without_a_dashboard_and_only_once(hass, entry):
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    entry.options.update(notifications_enabled=True, movement_notifications_enabled=False)
    entry.options["traps"][0].update(inspection_interval_days=1, inspection_notifications_enabled=True)
    with (
        patch("custom_components.mousetrap_manager.manager.dt_util.utcnow", return_value=now),
        patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create,
    ):
        manager = await start(hass, entry)
        assert not manager.summary("a")["inspection_due"]
        create.assert_not_called()
    due = now + timedelta(days=1)
    with (
        patch("custom_components.mousetrap_manager.manager.dt_util.utcnow", return_value=due),
        patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create,
    ):
        manager._tick(due)
        manager._tick(due)
        assert manager.summary("a")["inspection_due"]
        assert create.call_count == 1
        assert create.call_args.kwargs["notification_id"] == "mousetrap_manager_inspection_a"
        # A movement does not cause a second or different notification when movement notices are off.
        await manager._change(lambda ledger: ledger.movement("a", due.isoformat()))
        assert create.call_count == 1
        pending = manager.ledger.summary("a")["pending_event_id"]
        await manager.async_acknowledge("a", pending, False)
        assert not manager.summary("a")["inspection_due"]
    with (
        patch("custom_components.mousetrap_manager.manager.dt_util.utcnow", return_value=due + timedelta(days=1)),
        patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create,
    ):
        entry.options["notifications_enabled"] = False
        manager._tick(due + timedelta(days=1))
        assert manager.summary("a")["inspection_due"]
        create.assert_not_called()
    manager.async_stop()


async def test_pinned_maintenance_commands_are_idempotent_and_survive_storage(hass, entry):
    manager = await start(hass, entry)
    results = await asyncio.gather(*[manager.async_maintenance("a", "bait_replaced", "initial") for _ in range(10)])
    assert sum(results) == 1
    assert len([e for e in manager.ledger.data["events"] if e["type"] == "bait_replaced"]) == 1
    results = await asyncio.gather(
        *[manager.async_maintenance("a", "inspection_completed", "initial") for _ in range(10)]
    )
    assert sum(results) == 1
    persisted = manager._store.async_save.call_args.args[0]
    restored = TrapManager(hass, entry)
    restored._store = SimpleNamespace(async_load=AsyncMock(return_value=persisted), async_save=AsyncMock())
    with patch(
        "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
        new_callable=AsyncMock,
        return_value=lambda: None,
    ):
        await restored.async_start()
    assert restored.summary("a")["last_bait_replaced"] == manager.summary("a")["last_bait_replaced"]
    assert restored.summary("a")["last_inspection"] == manager.summary("a")["last_inspection"]
    assert not await restored.async_maintenance("a", "bait_replaced", "initial")
    assert CatchCount(restored).native_value == 0
    manager.async_stop()
    restored.async_stop()
