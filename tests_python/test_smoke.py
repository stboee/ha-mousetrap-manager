"""Load and unload the custom platforms using the actual HA integration loader."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.setup import async_setup_component


@pytest.mark.parametrize("recovery_enabled", [False, True])
@pytest.mark.parametrize("include_victor", [False, True])
async def test_native_setup_creates_entities_and_unloads(tmp_path, recovery_enabled, include_victor):
    (tmp_path / "custom_components").symlink_to(Path("custom_components").resolve(), target_is_directory=True)
    hass = HomeAssistant(str(tmp_path))
    loader.async_setup(hass)
    hass.config_entries = ConfigEntries(hass, {})
    await hass.config_entries.async_initialize()
    device_registry.async_setup(hass)
    await device_registry.async_load(hass)
    await entity_registry.async_load(hass)
    hass.config.skip_pip = True
    hass.config.components.update(["mqtt", "http"])
    hass.http = MagicMock()
    hass.http.async_register_static_paths = AsyncMock()
    entry = ConfigEntry(
        domain="mousetrap_manager",
        title="Mousetrap Manager",
        data={},
        options={
            "traps": [{"id": "a", "name": "Loft", "device_id": "source", "topic": "zigbee2mqtt/Vibrasjon"}],
            "victor_recovery_enabled": recovery_enabled,
            "victor_entry_id": "existing-victor-entry",
        },
        source="user",
        unique_id="mousetrap_manager",
        version=1,
        minor_version=1,
        discovery_keys={},
        subentries_data=[],
    )
    if include_victor:
        source = ConfigEntry(
            domain="victorsmartkill",
            title="Existing Victor",
            data={},
            options={},
            source="user",
            unique_id="source",
            version=1,
            minor_version=1,
            discovery_keys={},
            subentries_data=[],
        )
        hass.config_entries._entries[source.entry_id] = source
        device = device_registry.async_get(hass).async_get_or_create(
            config_entry_id=source.entry_id,
            identifiers={("victorsmartkill", "test:1")},
            name="Existing Victor",
            model="M1",
        )
        capture = entity_registry.async_get(hass).async_get_or_create(
            "binary_sensor", "victorsmartkill", "victorsmartkill_1_capture", config_entry=source, device_id=device.id
        )
        hass.states.async_set(capture.entity_id, "off")
        entry.options["traps"].append({"id": "v", "type": "victor", "device_id": device.id, "name": "Victor"})
    hass.config_entries._entries[entry.entry_id] = entry
    try:
        with patch(
            "custom_components.mousetrap_manager.manager.mqtt.async_subscribe",
            new_callable=AsyncMock,
            return_value=lambda: None,
        ):
            assert await async_setup_component(hass, "mousetrap_manager", {})
            await hass.async_block_till_done()
            assert entry.state is ConfigEntryState.LOADED
            states = hass.states.async_all()
            assert len([s for s in states if s.attributes.get("mousetrap_manager")]) == (2 if include_victor else 1)
            assert len([s for s in states if s.attributes.get("state_class") == "total"]) == 2
            assert any(s.entity_id.startswith("binary_sensor.") and s.state == "off" for s in states)
            assert len([s for s in states if s.entity_id.startswith("button.")]) == (4 if include_victor else 2)
            ages = [s for s in states if s.attributes.get("device_class") == "duration"]
            assert len(ages) == (4 if include_victor else 2)
            assert all(s.state == "unknown" and s.attributes["unit_of_measurement"] == "d" for s in ages)
            timestamps = [s for s in states if s.attributes.get("device_class") == "timestamp"]
            assert len(timestamps) == (7 if include_victor else 4)
            if include_victor:
                extra = [s for s in states if s.attributes.get("trap_id") == "v"]
                assert len(extra) == 1 and extra[0].state == "monitoring"
                assert extra[0].attributes["presentation"]["label"] == "Ingen fangst meldt"
                assert not any("catch_count" in s.attributes for s in extra)
                managed = entity_registry.async_get(hass).async_get(extra[0].entity_id)
                assert device_registry.async_get(hass).async_get(managed.device_id).via_device_id == device.id
                assert device_registry.async_get(hass).async_get(device.id).model == "M1"
            recovery = hass.data["mousetrap_manager"][entry.entry_id].victor_recovery
            diagnostic = [s for s in states if s.attributes.get("device_class") == "enum"]
            assert len(diagnostic) == 1
            assert diagnostic[0].state == ("starting" if recovery_enabled else "disabled")
            assert await hass.config_entries.async_unload(entry.entry_id)
            assert recovery._stopped
    finally:
        await hass.async_stop()
