"""Recovery reacts to real HA entity states, with no Victor API or credentials."""

import asyncio
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from custom_components.mousetrap_manager.victor_recovery import RECOVERY_DEFAULTS, VictorRecovery


@pytest.fixture
async def env(tmp_path):
    hass = HomeAssistant(str(tmp_path))
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    dr.async_setup(hass)
    await dr.async_load(hass)
    await er.async_load(hass)
    registry = er.async_get(hass)
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
    target._async_set_state(hass, ConfigEntryState.LOADED, None)
    entities = [
        registry.async_get_or_create("sensor", "victorsmartkill", key, config_entry=target).entity_id
        for key in ("trap_one", "trap_two")
    ]
    for entity_id in entities:
        hass.states.async_set(entity_id, "unavailable")
    owner = SimpleNamespace(
        entry_id="manager",
        options={
            **RECOVERY_DEFAULTS,
            "victor_recovery_enabled": True,
            "victor_entry_id": target.entry_id,
        },
    )
    recovery = VictorRecovery(hass, owner)
    recovery._store = SimpleNamespace(async_load=AsyncMock(return_value=None), async_save=AsyncMock())
    hass.set_state(CoreState.running)
    now = datetime(2026, 11, 1, 10, tzinfo=timezone.utc)
    clock = MagicMock(return_value=now)
    with (
        patch("custom_components.mousetrap_manager.victor_recovery.dt_util.utcnow", clock),
        patch.object(type(hass.config_entries), "async_reload", new_callable=AsyncMock, return_value=True) as reload,
    ):
        await recovery.async_start()
        await hass.async_block_till_done()
        yield SimpleNamespace(
            hass=hass,
            target=target,
            entities=entities,
            owner=owner,
            recovery=recovery,
            reload=reload,
            clock=clock,
            now=now,
        )
        await recovery.async_shutdown()
    await hass.async_stop()


async def advance(env, minutes):
    env.clock.return_value = env.now + timedelta(minutes=minutes)
    await env.recovery.async_check()


async def test_only_sustained_failure_reloads_selected_entry(env):
    assert env.recovery.status == "waiting"
    await advance(env, 19)
    env.reload.assert_not_called()
    await advance(env, 20)
    env.reload.assert_awaited_once_with(env.target.entry_id)
    assert env.recovery.data["attempts"] == 1
    assert env.recovery.data["last_result"] == "completed"
    await advance(env, 21)
    await advance(env, 40)
    assert env.recovery.status == "cooldown"
    env.reload.assert_awaited_once()
    await advance(env, 80)
    assert env.reload.await_count == 2


async def test_transient_recovery_restarts_continuous_failure_wait(env):
    env.clock.return_value = env.now + timedelta(minutes=10)
    env.hass.states.async_set(env.entities[0], 95)
    await env.hass.async_block_till_done()
    assert env.recovery.status == "monitoring"
    env.clock.return_value = env.now + timedelta(minutes=11)
    env.hass.states.async_set(env.entities[0], "unavailable")
    await env.hass.async_block_till_done()
    await advance(env, 30)
    env.reload.assert_not_called()
    await advance(env, 31)
    env.reload.assert_awaited_once()


async def test_one_unavailable_trap_does_not_reload_healthy_account(env):
    env.hass.states.async_set(env.entities[1], 66, {"last_report_date": "2025-01-01T00:00:00Z"})
    await env.hass.async_block_till_done()
    await advance(env, 1000)
    env.reload.assert_not_called()
    assert env.recovery.status == "monitoring"


@pytest.mark.parametrize("value,attrs", [("unknown", {}), ("unavailable", {"restored": True})])
async def test_unknown_or_restored_entities_are_not_proof_of_an_outage(env, value, attrs):
    for entity_id in env.entities:
        env.hass.states.async_set(entity_id, value, attrs)
    await env.hass.async_block_till_done()
    await advance(env, 100)
    env.reload.assert_not_called()


async def test_attempts_are_saved_before_reload_and_limited_per_outage(env):
    async def check_durable_before_reload(entry_id):
        saved = env.recovery._store.async_save.call_args.args[0]
        assert saved["last_result"] == "started"
        assert saved["last_attempt"] == env.clock.return_value.isoformat()
        return False

    env.reload.side_effect = check_durable_before_reload
    for minute in (20, 80, 140, 200):
        await advance(env, minute)
    assert env.reload.await_count == 3
    assert env.recovery.status == "limit_reached"
    assert env.recovery.data["last_result"] == "failed"
    env.hass.states.async_set(env.entities[0], 95)
    await env.hass.async_block_till_done()
    assert env.recovery.data["attempts"] == 0
    assert env.recovery.data["last_attempt"] == (env.now + timedelta(minutes=140)).isoformat()


async def test_restart_preserves_cooldown_and_attempt_count_but_waits_again(env):
    await advance(env, 20)
    saved = env.recovery.data
    await env.recovery.async_shutdown()
    replacement = VictorRecovery(env.hass, env.owner)
    replacement._store = SimpleNamespace(async_load=AsyncMock(return_value=saved), async_save=AsyncMock())
    env.clock.return_value = env.now + timedelta(minutes=25)
    await replacement.async_start()
    await env.hass.async_block_till_done()
    assert replacement.data["attempts"] == 1
    assert replacement.status == "waiting"
    env.clock.return_value = env.now + timedelta(minutes=45)
    await replacement.async_check()
    assert replacement.status == "cooldown"
    env.reload.assert_awaited_once()
    await replacement.async_shutdown()


@pytest.mark.parametrize(
    "state",
    [
        ConfigEntryState.SETUP_RETRY,
        ConfigEntryState.NOT_LOADED,
        ConfigEntryState.SETUP_IN_PROGRESS,
        ConfigEntryState.UNLOAD_IN_PROGRESS,
        ConfigEntryState.MIGRATION_ERROR,
        ConfigEntryState.FAILED_UNLOAD,
    ],
)
async def test_does_not_interfere_with_ha_retry_or_manual_lifecycle(env, state):
    env.target._async_set_state(env.hass, state, None)
    await advance(env, 100)
    env.reload.assert_not_called()


async def test_authentication_flow_is_never_aborted_by_reload(env):
    with patch.object(ConfigEntry, "async_get_active_flows", return_value=[{"context": {"source": "reauth"}}]):
        await advance(env, 100)
    env.reload.assert_not_called()
    assert env.recovery.status == "auth_required"


async def test_rechecks_authentication_after_saving_attempt(env):
    auth = False

    async def auth_started_during_save(data):
        nonlocal auth
        auth = True

    env.recovery._store.async_save.side_effect = auth_started_during_save
    with patch.object(ConfigEntry, "async_get_active_flows", side_effect=lambda *_: [True] if auth else []):
        await advance(env, 20)
    env.reload.assert_not_called()
    assert env.recovery.status == "auth_required"
    assert env.recovery.data["attempts"] == 0


async def test_storage_failure_does_not_reload_without_a_durable_attempt(env):
    env.recovery._store.async_save.side_effect = OSError("disk full")
    await advance(env, 20)
    env.reload.assert_not_called()
    assert env.recovery.status == "storage_error"


async def test_concurrent_checks_do_not_start_parallel_reloads_and_shutdown_waits(env):
    entered = asyncio.Event()
    finish = asyncio.Event()

    async def slow_reload(entry_id):
        entered.set()
        await finish.wait()
        return True

    env.reload.side_effect = slow_reload
    env.clock.return_value = env.now + timedelta(minutes=20)
    env.recovery.async_request_check()
    await entered.wait()
    await asyncio.gather(*[env.recovery.async_check() for _ in range(10)])
    shutdown = asyncio.create_task(env.recovery.async_shutdown())
    await asyncio.sleep(0)
    assert not shutdown.done()
    env.reload.assert_awaited_once()
    finish.set()
    await shutdown
    await advance(env, 1000)
    env.reload.assert_awaited_once()


async def test_default_off_creates_no_listener_or_reload(env):
    env.owner.options.pop("victor_recovery_enabled")
    disabled = VictorRecovery(env.hass, env.owner)
    disabled._store = SimpleNamespace(async_load=AsyncMock(), async_save=AsyncMock())
    await disabled.async_start()
    await disabled.async_check()
    assert disabled.status == "disabled"
    disabled._store.async_load.assert_not_called()
    env.reload.assert_not_called()


async def test_ha_startup_does_not_count_as_outage_time(env):
    env.hass.set_state(CoreState.starting)
    await advance(env, 100)
    env.hass.set_state(CoreState.running)
    await advance(env, 101)
    await advance(env, 120)
    env.reload.assert_not_called()
    await advance(env, 121)
    env.reload.assert_awaited_once()


async def test_explicit_attempt_reset_retains_the_last_reload_cooldown(env):
    saved = {
        "entry_id": env.target.entry_id,
        "attempts": 3,
        "last_attempt": env.now.isoformat(),
        "last_result": "failed",
    }
    owner = SimpleNamespace(
        entry_id="manager", options={**env.owner.options, "victor_recovery_reset_token": "user-reset"}
    )
    replacement = VictorRecovery(env.hass, owner)
    replacement._store = SimpleNamespace(async_load=AsyncMock(return_value=saved), async_save=AsyncMock())
    await replacement.async_start()
    await env.hass.async_block_till_done()
    assert replacement.data["attempts"] == 0
    assert replacement.data["last_attempt"] == env.now.isoformat()
    await replacement.async_shutdown()


async def test_disabled_entry_is_not_automatically_enabled(env):
    from homeassistant.config_entries import ConfigEntryDisabler

    env.target.disabled_by = ConfigEntryDisabler.USER
    await advance(env, 100)
    assert env.recovery.status == "not_loaded"
    env.reload.assert_not_called()


async def test_setup_error_can_be_reloaded_after_waiting(env):
    env.target._async_set_state(env.hass, ConfigEntryState.SETUP_ERROR, "connection failed")
    await advance(env, 20)
    env.reload.assert_awaited_once_with(env.target.entry_id)


async def test_disabling_recovery_during_the_reservation_prevents_reload(env):
    async def disabled_during_save(data):
        env.recovery.stop()

    env.recovery._store.async_save.side_effect = disabled_during_save
    await advance(env, 20)
    env.reload.assert_not_called()
    assert env.recovery.data["attempts"] == 0


async def test_reload_exception_is_recorded_and_not_retried_immediately(env):
    env.reload.side_effect = RuntimeError("temporary error")
    await advance(env, 20)
    assert env.recovery.data["last_result"] == "error"
    await advance(env, 40)
    assert env.recovery.status == "cooldown"
    env.reload.assert_awaited_once()
