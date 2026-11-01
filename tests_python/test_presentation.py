"""Reference-based Victor display and shared server-side presentation decisions."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntries, ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.mousetrap_manager.config_flow import MousetrapOptionsFlow
from custom_components.mousetrap_manager.ledger import LedgerError
from custom_components.mousetrap_manager.manager import TrapManager
from custom_components.mousetrap_manager.presentation import SOURCE_SUFFIXES, source_entities
from custom_components.mousetrap_manager.sensor import MaintenanceSensor, TrapStatus
from custom_components.mousetrap_manager.sensor import async_setup_entry as setup_sensors


@pytest.fixture
async def env(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    await ar.async_load(hass)
    target = ConfigEntry(
        domain="victorsmartkill",
        title="Victor",
        data={},
        options={},
        source="user",
        unique_id="victor",
        version=1,
        minor_version=1,
        discovery_keys={},
        subentries_data=[],
    )
    hass.config_entries._entries[target.entry_id] = target
    area = ar.async_get(hass).async_create("Uthus")
    device = dr.async_get(hass).async_get_or_create(
        config_entry_id=target.entry_id, identifiers={("victorsmartkill", "IDSN:1:123")}, name="M1", model="M1"
    )
    dr.async_get(hass).async_update_device(device.id, area_id=area.id)
    sources = {}
    for role, suffix in SOURCE_SUFFIXES.items():
        sources[role] = (
            er.async_get(hass)
            .async_get_or_create(
                "binary_sensor" if role == "capture" else "sensor",
                "victorsmartkill",
                "victorsmartkill_1_" + suffix,
                config_entry=target,
                device_id=device.id,
                suggested_object_id="m1_" + suffix,
            )
            .entity_id
        )
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    values = {
        "capture": "off",
        "present": 0,
        "catches": 4,
        "last_catch": "2025-10-24T15:57:04+00:00",
        "contact": now.isoformat(),
        "battery": 95,
        "signal": -57,
    }
    for role, value in values.items():
        hass.states.async_set(sources[role], value)
    config = {"id": "v", "type": "victor", "device_id": device.id, "name": "Victor", "inspection_interval_days": 7}
    entry = SimpleNamespace(entry_id="owner", options={"traps": [config]})
    manager = TrapManager(hass, entry)
    manager._store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    with patch("custom_components.mousetrap_manager.manager.mqtt.async_subscribe", new_callable=AsyncMock) as mqtt:
        await manager.async_start()
        yield SimpleNamespace(
            hass=hass, manager=manager, config=config, sources=sources, now=now, mqtt=mqtt, target=target
        )
    await manager.async_shutdown()
    await hass.async_stop()


def model(env, offset=0):
    return env.manager.summary("v", env.now + timedelta(hours=offset))["presentation"]


async def test_native_victor_values_are_references_not_imported_catches(env):
    p = model(env)
    assert p["label"] == "Ingen fangst meldt"
    assert p["location"] == "Uthus"
    assert next(m for m in p["metrics"] if m["key"] == "catches") == {
        "key": "catches",
        "label": "Fangster",
        "entity_id": env.sources["catches"],
    }
    assert env.manager.ledger.catches() == []
    env.mqtt.assert_not_called()
    env.hass.data["mousetrap_manager"] = {"owner": env.manager}
    entities = []
    await setup_sensors(env.hass, env.manager.entry, entities.extend)
    assert not any(e.trap_id == "v" and e.unique_id.endswith("catch_count") for e in entities)
    assert not any(e.trap_id == "v" and e.unique_id.endswith("last_sensor_contact") for e in entities)
    assert MaintenanceSensor(env.manager, "v", "bait_age_days").state_class is None
    assert TrapStatus(env.manager, env.config).device_info["via_device_id"] == env.config["device_id"]
    assert "catch_count" not in TrapStatus(env.manager, env.config).extra_state_attributes


async def test_inspection_and_bait_never_acknowledge_or_count_victor_capture(env):
    env.hass.states.async_set(env.sources["capture"], "on")
    env.hass.states.async_set(env.sources["present"], 1)
    assert model(env)["label"] == "Fangst meldt"
    assert [a["service"] for a in model(env)["actions"]] == ["inspection_completed", "bait_replaced"]
    await env.manager.async_maintenance("v", "inspection_completed", "initial")
    await env.manager.async_maintenance("v", "bait_replaced", "initial")
    assert model(env)["label"] == "Fangst meldt"
    assert env.hass.states.get(env.sources["capture"]).state == "on"
    assert env.hass.states.get(env.sources["catches"]).state == "4"
    assert env.manager.ledger.catches() == []
    assert env.manager.ledger.journal("v")[1]["bait_inspected"] is True
    with pytest.raises(LedgerError, match="Victor"):
        await env.manager.async_acknowledge("v", "anything", True)


async def test_source_rename_is_resolved_by_stable_identity(env):
    registry = er.async_get(env.hass)
    old = env.sources["capture"]
    registry.async_update_entity(old, new_entity_id="binary_sensor.renamed_capture")
    env.hass.states.async_set("binary_sensor.renamed_capture", "on")
    assert source_entities(env.hass, env.config)["capture"] == "binary_sensor.renamed_capture"
    assert model(env)["status"] == "capture"


async def test_source_outage_and_old_contact_are_different(env):
    assert model(env, 25)["status"] == "warning"
    assert model(env, 73)["label"] == "Ingen sensorkontakt innen fristen"
    assert model(env, 73)["health"]["unavailable"] is False
    for entity_id in env.sources.values():
        env.hass.states.async_set(entity_id, "unavailable")
    assert model(env)["status"] == "unavailable"
    assert TrapStatus(env.manager, env.config).native_value == "source_unavailable"
    env.hass.states.async_set(env.sources["battery"], "95")
    assert model(env)["status"] == "unknown"


async def test_unknown_restored_future_contact_never_invents_a_report(env):
    for value in ("unknown", (env.now + timedelta(days=1)).isoformat()):
        env.hass.states.async_set(env.sources["contact"], value)
        assert model(env)["last_sensor_contact"] is None
    env.hass.states.async_set(env.sources["contact"], env.now.isoformat(), {"restored": True})
    assert model(env)["last_sensor_contact"] is None


async def test_global_settings_per_trap_override_and_disabled_thresholds(env):
    env.manager.entry.options["display"] = {"battery_low": 99, "show_scene": False, "metrics": ["battery"]}
    assert model(env)["label"] == "Lavt batteri"
    assert model(env)["show_scene"] is False
    env.config["display"] = {"battery_low": 10, "stale_after_hours": 0, "offline_after_hours": 0}
    env.config["inspection_interval_days"] = 0
    assert model(env, 500)["status"] == "monitoring"
    assert len(model(env)["metrics"]) == 1


async def test_source_state_updates_dispatch_shared_view_without_polling_dashboard(env):
    with patch("custom_components.mousetrap_manager.manager.async_dispatcher_send") as dispatch:
        env.hass.states.async_set(env.sources["capture"], "on")
        await env.hass.async_block_till_done()
        assert dispatch.called
        assert model(env)["status"] == "capture"
    assert not env.manager._store.async_save.call_args.args[0]["events"][-1]["type"] == "capture_confirmed"


async def test_options_register_victor_without_mqtt_and_keep_existing_settings(env):
    entry = env.target
    env.hass.config_entries.async_update_entry(entry, options={"traps": [], "notifications_enabled": False})
    flow = MousetrapOptionsFlow()
    flow.hass = env.hass
    flow.handler = entry.entry_id
    flow.flow_id = "options"
    result = await flow.async_step_add_victor(
        {"name": "M1", "device_id": env.config["device_id"], "inspection_interval_days": 14}
    )
    config = result["data"]["traps"][0]
    assert config["type"] == "victor" and "topic" not in config
    assert config["inspection_interval_days"] == 14
    assert not result["data"]["notifications_enabled"]
    result = await flow.async_step_display({"stale_after_hours": 100, "offline_after_hours": 24})
    assert result["errors"]["offline_after_hours"] == "invalid_thresholds"


async def test_notifications_master_off_and_optional_health_notices(env):
    env.hass.states.async_set(env.sources["battery"], "5")
    env.manager.entry.options["health_notifications_enabled"] = True
    with patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create:
        env.manager._sync_notifications()
        create.assert_not_called()
        env.manager.entry.options["notifications_enabled"] = True
        env.manager._sync_notifications()
        env.manager._sync_notifications()
        assert create.call_count == 1
        assert create.call_args.kwargs["notification_id"] == "mousetrap_manager_health_v"


async def test_attention_combines_reasons_counts_traps_once_and_orders_by_priority(env):
    from homeassistant.util import dt as dt_util

    env.manager.entry.options["traps"].append({"id": "a", "name": "Loft", "device_id": "snap", "topic": "z2m/snap"})
    await env.manager._change(lambda ledger: ledger.sync_traps(env.manager.traps, env.now.isoformat()))
    await env.manager._change(lambda ledger: ledger.movement("a", env.now.isoformat()))
    env.hass.states.async_set(env.sources["capture"], "on")
    env.hass.states.async_set(env.sources["present"], 1)
    before = env.manager.ledger.clone().data
    view = env.manager.attention(dt_util.utcnow() + timedelta(days=8))
    assert view["count"] == 2
    assert view["summary"] == "2 feller trenger tilsyn"
    assert [item["trap_id"] for item in view["items"]] == ["v", "a"]
    assert [r["code"] for r in view["items"][0]["reasons"]] == ["capture", "inspection"]
    assert view["items"][0]["reason_text"] == "Fangst meldt · Inspeksjon nødvendig"
    assert env.manager.ledger.data == before
    assert not env.manager.ledger.catches()


async def test_attention_add_archive_and_acknowledge_update_live_without_manual_lists(env):
    env.config["inspection_interval_days"] = 0
    assert env.manager.attention(env.now)["count"] == 0
    env.manager.entry.options["traps"].append({"id": "a", "name": "Loft", "topic": "z2m/a", "device_id": "snap"})
    await env.manager._change(lambda ledger: ledger.sync_traps(env.manager.traps, env.now.isoformat()))
    await env.manager._change(lambda ledger: ledger.movement("a", env.now.isoformat()))
    assert env.manager.attention(env.now)["count"] == 1
    event = env.manager.ledger.summary("a")["pending_event_id"]
    await env.manager.async_acknowledge("a", event, False)
    assert env.manager.attention(env.now)["count"] == 0
    env.hass.states.async_set(env.sources["capture"], "on")
    assert env.manager.attention(env.now)["count"] == 1
    env.config["archived"] = True
    await env.manager._change(lambda ledger: ledger.sync_traps(env.manager.traps, env.now.isoformat()))
    assert env.manager.attention(env.now)["count"] == 0


async def test_attention_health_is_configurable_and_independent_of_notifications(env):
    env.config["inspection_interval_days"] = 0
    env.hass.states.async_set(env.sources["battery"], 5)
    assert env.manager.attention(env.now + timedelta(hours=80))["count"] == 0
    env.manager.entry.options["attention"] = {"include_contact": True, "include_battery": True}
    with patch("custom_components.mousetrap_manager.manager.persistent_notification.async_create") as create:
        view = env.manager.attention(env.now + timedelta(hours=80))
        env.manager._sync_notifications()
        create.assert_not_called()
    assert view["count"] == 1
    assert [r["code"] for r in view["items"][0]["reasons"]] == ["contact_overdue", "battery"]
    env.hass.states.async_set(env.sources["contact"], "unknown")
    assert env.manager.attention(env.now)["items"][0]["reasons"][0]["code"] == "contact_unknown"
    env.hass.states.async_set(env.sources["capture"], "on")
    env.manager.entry.options["attention"].update(include_capture=False, include_contact=False, include_battery=False)
    assert env.manager.attention(env.now)["count"] == 0


async def test_attention_source_unknown_unavailable_and_inspection_do_not_clear_victor(env):
    env.config["inspection_interval_days"] = 0
    for entity_id in env.sources.values():
        env.hass.states.async_set(entity_id, "unavailable")
    assert env.manager.attention(env.now)["items"][0]["reasons"][0]["code"] == "source_unavailable"
    env.hass.states.async_set(env.sources["battery"], 95)
    assert env.manager.attention(env.now)["items"][0]["reasons"][0]["code"] == "source_unknown"
    env.hass.states.async_set(env.sources["capture"], "on")
    await env.manager.async_maintenance("v", "inspection_completed", "initial")
    assert env.manager.attention(env.now)["items"][0]["reasons"][0]["code"] == "capture"
    assert not env.manager.ledger.catches()
    env.manager.entry.options["attention"] = {"include_capture": False, "include_source_problems": False}
    assert env.manager.attention(env.now)["count"] == 0


@pytest.mark.parametrize(
    "path",
    ["https://example.com", "//example.com", "/\\\\example.com", "/bad path", "javascript:alert(1)", "/bad\npath"],
)
async def test_attention_options_reject_non_internal_paths(env, path):
    flow = MousetrapOptionsFlow()
    flow.hass, flow.handler, flow.flow_id = env.hass, env.target.entry_id, "attention-flow"
    result = await flow.async_step_attention({"navigation_path": path})
    assert result["errors"]["navigation_path"] == "invalid_navigation_path"


async def test_attention_options_preserve_traps_and_recovery_config(env):
    env.hass.config_entries.async_update_entry(
        env.target, options={"traps": [env.config], "victor_recovery_enabled": True}
    )
    flow = MousetrapOptionsFlow()
    flow.hass, flow.handler, flow.flow_id = env.hass, env.target.entry_id, "attention-flow"
    form = await flow.async_step_attention()
    values = form["data_schema"]({})
    assert values["include_capture"] and values["include_movement"] and values["include_inspection"]
    assert values["include_source_problems"] and not values["include_battery"] and not values["include_contact"]
    result = await flow.async_step_attention({"navigation_path": "/dashboard-hjem/musefeller?view=full#top"})
    assert result["type"] == "create_entry"
    assert result["data"]["traps"] == [env.config]
    assert result["data"]["victor_recovery_enabled"] is True
    assert result["data"]["attention"]["navigation_path"].startswith("/dashboard-hjem/")
