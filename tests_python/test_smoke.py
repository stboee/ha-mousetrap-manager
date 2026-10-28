"""Load and unload the custom platforms using the actual HA integration loader."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant import loader
from homeassistant.config_entries import ConfigEntries, ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry, entity_registry
from homeassistant.setup import async_setup_component


async def test_native_setup_creates_entities_and_unloads(tmp_path):
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
        options={"traps": [{"id": "a", "name": "Loft", "device_id": "source", "topic": "zigbee2mqtt/Vibrasjon"}]},
        source="user",
        unique_id="mousetrap_manager",
        version=1,
        minor_version=1,
        discovery_keys={},
        subentries_data=[],
    )
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
            assert len([s for s in states if s.attributes.get("mousetrap_manager")]) == 1
            assert len([s for s in states if s.attributes.get("state_class") == "total"]) == 2
            assert any(s.entity_id.startswith("binary_sensor.") and s.state == "off" for s in states)
            assert await hass.config_entries.async_unload(entry.entry_id)
    finally:
        await hass.async_stop()
