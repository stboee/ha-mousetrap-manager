"""One central integration with trap registration and admin-only correction."""

from copy import deepcopy
from uuid import uuid4

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .const import DEFAULT_COOLDOWN, DOMAIN
from .ledger import LedgerError


def valid_topic(topic):
    return (
        isinstance(topic, str)
        and bool(topic.strip())
        and topic == topic.strip()
        and not any(c in topic for c in ("#", "+", "\x00"))
    )


class MousetrapConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="Mousetrap Manager", data={})
        return self.async_show_form(step_id="user", data_schema=vol.Schema({}))

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return MousetrapOptionsFlow()


class MousetrapOptionsFlow(config_entries.OptionsFlow):
    def _options(self):
        return {
            "traps": [],
            "notifications_enabled": False,
            "cooldown_seconds": DEFAULT_COOLDOWN,
            **deepcopy(dict(self.config_entry.options)),
        }

    def _manager(self):
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["add_trap", "edit_trap", "settings", "undo"])

    async def async_step_add_trap(self, user_input=None):
        return await self._trap_form("add_trap", user_input)

    async def async_step_edit_trap(self, user_input=None):
        traps = self._options()["traps"]
        if not traps:
            return self.async_abort(reason="no_traps")
        if user_input:
            self._editing = user_input["trap_id"]
            return await self.async_step_edit_details()
        return self.async_show_form(
            step_id="edit_trap",
            data_schema=vol.Schema(
                {
                    vol.Required("trap_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[
                                {"value": t["id"], "label": t["name"] + (" (arkivert)" if t.get("archived") else "")}
                                for t in traps
                            ],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_details(self, user_input=None):
        return await self._trap_form("edit_details", user_input, self._editing)

    async def _trap_form(self, step_id, user_input, editing=None):
        options = self._options()
        existing = next((t for t in options["traps"] if t["id"] == editing), {})
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input["name"] = user_input["name"].strip()
            if not user_input["name"]:
                errors["name"] = "empty_name"
            if not valid_topic(user_input["topic"]):
                errors["topic"] = "invalid_topic"
            device = dr.async_get(self.hass).async_get(user_input["device_id"])
            if device is None:
                errors["device_id"] = "unknown_device"
            if any(
                t["id"] != editing
                and (t.get("device_id") == user_input["device_id"] or t["topic"] == user_input["topic"])
                for t in options["traps"]
            ):
                errors["base"] = "already_registered"
            if not errors:
                trap = {**existing, **user_input, "id": editing or uuid4().hex}
                if editing:
                    options["traps"] = [trap if t["id"] == editing else t for t in options["traps"]]
                else:
                    options["traps"].append(trap)
                return self.async_create_entry(title="", data=options)
            existing = {**existing, **user_input}
        schema = {
            vol.Required("name", default=existing.get("name", "")): str,
            vol.Required(
                "device_id", **({"default": existing["device_id"]} if existing.get("device_id") else {})
            ): selector.DeviceSelector(selector.DeviceSelectorConfig(integration="mqtt")),
            vol.Required("topic", default=existing.get("topic", "zigbee2mqtt/Vibrasjon")): str,
        }
        if editing:
            schema[vol.Required("archived", default=existing.get("archived", False))] = bool
        return self.async_show_form(step_id=step_id, data_schema=vol.Schema(schema), errors=errors)

    async def async_step_settings(self, user_input=None):
        options = self._options()
        if user_input is not None:
            options.update(user_input)
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required("notifications_enabled", default=options["notifications_enabled"]): bool,
                    vol.Required("cooldown_seconds", default=options["cooldown_seconds"]): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=600, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s"
                        )
                    ),
                }
            ),
        )

    async def async_step_undo(self, user_input=None):
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_loaded")
        choices = []
        for trap_id, trap in manager.ledger.data["traps"].items():
            catches = manager.ledger.catches(trap_id)
            if catches:
                choices.append({"value": trap_id, "label": trap["name"]})
        if not choices:
            return self.async_abort(reason="no_captures")
        if user_input is not None:
            self._undo_trap = user_input["trap_id"]
            catches = manager.ledger.catches(self._undo_trap)
            if not catches:
                return self.async_abort(reason="no_captures")
            self._undo_capture = catches[-1]
            return await self.async_step_undo_confirm()
        return self.async_show_form(
            step_id="undo",
            data_schema=vol.Schema(
                {
                    vol.Required("trap_id"): selector.SelectSelector(selector.SelectSelectorConfig(options=choices)),
                }
            ),
        )

    async def async_step_undo_confirm(self, user_input=None):
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_loaded")
        errors = {}
        if user_input is not None:
            if not user_input.get("confirm"):
                errors["confirm"] = "confirmation_required"
            else:
                try:
                    await manager.async_undo(self._undo_trap, self._undo_capture["id"])
                except LedgerError:
                    return self.async_abort(reason="capture_changed")
                return self.async_abort(reason="capture_undone")
        return self.async_show_form(
            step_id="undo_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("confirm", default=False): bool,
                }
            ),
            errors=errors,
            description_placeholders={
                "trap": manager.ledger.summary(self._undo_trap)["name"],
                "timestamp": self._undo_capture["at"],
            },
        )
