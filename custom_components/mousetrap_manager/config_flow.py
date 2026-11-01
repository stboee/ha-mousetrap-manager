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
from .presentation import DISPLAY_DEFAULTS, METRIC_LABELS, SOURCE_SUFFIXES, display_settings
from .victor_recovery import RECOVERY_DEFAULTS


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
            "movement_notifications_enabled": self.config_entry.options.get("notifications_enabled", False),
            "cooldown_seconds": DEFAULT_COOLDOWN,
            **deepcopy(dict(self.config_entry.options)),
        }

    def _manager(self):
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_trap", "add_victor", "edit_trap", "display", "settings", "victor_recovery", "undo"],
        )

    async def async_step_victor_recovery(self, user_input=None):
        options = self._options()
        values = {**RECOVERY_DEFAULTS, **options}
        errors = {}
        if user_input is not None:
            values.update(user_input)
            target_id = values.get("victor_entry_id")
            target = self.hass.config_entries.async_get_entry(target_id) if target_id else None
            if values["victor_recovery_enabled"] and (target is None or target.domain != "victorsmartkill"):
                errors["victor_entry_id"] = "invalid_victor_entry"
            for key, low, high in (
                ("victor_unavailable_minutes", 1, 1440),
                ("victor_reload_cooldown_minutes", 5, 1440),
                ("victor_reload_max_attempts", 1, 10),
            ):
                try:
                    value = values[key]
                    if isinstance(value, bool) or int(value) != float(value) or not low <= int(value) <= high:
                        raise ValueError
                    values[key] = int(value)
                except ValueError, TypeError, OverflowError:
                    errors[key] = "invalid_recovery_number"
            if not errors:
                options.update({key: values[key] for key in RECOVERY_DEFAULTS})
                if target_id:
                    options["victor_entry_id"] = target_id
                if values.get("reset_attempts"):
                    options["victor_recovery_reset_token"] = uuid4().hex
                return self.async_create_entry(title="", data=options)
        schema = {vol.Required("victor_recovery_enabled", default=values["victor_recovery_enabled"]): bool}
        selected = values.get("victor_entry_id")
        schema[vol.Optional("victor_entry_id", **({"default": selected} if selected else {}))] = (
            selector.ConfigEntrySelector(selector.ConfigEntrySelectorConfig(integration="victorsmartkill"))
        )
        for key, low, high in (
            ("victor_unavailable_minutes", 1, 1440),
            ("victor_reload_cooldown_minutes", 5, 1440),
            ("victor_reload_max_attempts", 1, 10),
        ):
            schema[vol.Required(key, default=values[key])] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=low, max=high, step=1, mode=selector.NumberSelectorMode.BOX)
            )
        schema[vol.Required("reset_attempts", default=False)] = bool
        return self.async_show_form(step_id="victor_recovery", data_schema=vol.Schema(schema), errors=errors)

    async def async_step_add_trap(self, user_input=None):
        return await self._trap_form("add_trap", user_input)

    async def async_step_add_victor(self, user_input=None):
        return await self._trap_form("add_victor", user_input, kind="victor")

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

    @staticmethod
    def _display_schema(values, global_settings=False):
        schema = {}
        if global_settings:
            schema[vol.Required("title", default=values["title"])] = str
            schema[vol.Required("sort", default=values["sort"])] = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=[
                        {"value": v, "label": label}
                        for v, label in (("config", "Registreringsrekkefølge"), ("status", "Status"), ("name", "Navn"))
                    ]
                )
            )
            schema[vol.Required("columns", default=values["columns"])] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=1, max=6, step=1, mode=selector.NumberSelectorMode.BOX)
            )
            schema[vol.Required("show_summary", default=values["show_summary"])] = bool
        for key in ("show_scene", "animations"):
            schema[vol.Required(key, default=values[key])] = bool
        schema[vol.Required("metrics", default=values["metrics"])] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True, options=[{"value": k, "label": v} for k, v in METRIC_LABELS.items()]
            )
        )
        for key, maximum in (("battery_low", 100), ("stale_after_hours", 87600), ("offline_after_hours", 87600)):
            schema[vol.Required(key, default=values[key])] = selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=maximum, step=1, mode=selector.NumberSelectorMode.BOX)
            )
        return schema

    @staticmethod
    def _display_errors(values):
        errors = {}
        if values.get("offline_after_hours") and values.get("stale_after_hours", 0) > values["offline_after_hours"]:
            errors["offline_after_hours"] = "invalid_thresholds"
        return errors

    async def async_step_display(self, user_input=None):
        options = self._options()
        values = display_settings(options)
        errors = {}
        if user_input is not None:
            values.update(user_input)
            errors = self._display_errors(values)
            if not errors:
                options["display"] = values
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="display", data_schema=vol.Schema(self._display_schema(values, True)), errors=errors
        )

    async def _trap_form(self, step_id, user_input, editing=None, kind=None):
        options = self._options()
        existing = next((t for t in options["traps"] if t["id"] == editing), {})
        kind = kind or existing.get("type", "snap")
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            user_input["name"] = user_input["name"].strip()
            if "inspection_interval_days" in user_input:
                try:
                    days = user_input["inspection_interval_days"]
                    if isinstance(days, bool) or int(days) != float(days) or not 0 <= int(days) <= 3650:
                        raise ValueError
                    user_input["inspection_interval_days"] = int(days)
                except TypeError, ValueError, OverflowError:
                    errors["inspection_interval_days"] = "invalid_interval"
            if not user_input["name"]:
                errors["name"] = "empty_name"
            if kind == "snap" and not valid_topic(user_input.get("topic")):
                errors["topic"] = "invalid_topic"
            device = dr.async_get(self.hass).async_get(user_input["device_id"])
            if device is None:
                errors["device_id"] = "unknown_device"
            if any(
                t["id"] != editing
                and (
                    t.get("device_id") == user_input["device_id"]
                    or (kind == "snap" and t.get("topic") == user_input.get("topic"))
                )
                for t in options["traps"]
            ):
                errors["base"] = "already_registered"
            override = user_input.pop("override_display", bool(existing.get("display")))
            display = {k: user_input.pop(k) for k in DISPLAY_DEFAULTS if k in user_input}
            if override:
                display = {**display_settings(options, existing), **display}
                errors.update(self._display_errors(display))
            sources = {
                role: user_input.pop("source_" + role) for role in SOURCE_SUFFIXES if "source_" + role in user_input
            }
            if not errors:
                trap = {**existing, **user_input, "id": editing or uuid4().hex}
                if kind == "victor":
                    trap["type"] = "victor"
                    trap["source_entities"] = sources
                if override:
                    trap["display"] = display
                else:
                    trap.pop("display", None)
                if editing:
                    options["traps"] = [trap if t["id"] == editing else t for t in options["traps"]]
                else:
                    options["traps"].append(trap)
                return self.async_create_entry(title="", data=options)
            existing = {**existing, **user_input, "display": display if override else {}}
        schema = {
            vol.Required("name", default=existing.get("name", "")): str,
            vol.Optional("location", default=existing.get("location", "")): str,
            vol.Required(
                "device_id", **({"default": existing["device_id"]} if existing.get("device_id") else {})
            ): selector.DeviceSelector(
                selector.DeviceSelectorConfig(integration="victorsmartkill" if kind == "victor" else "mqtt")
            ),
        }
        if kind == "snap":
            schema[vol.Required("topic", default=existing.get("topic", "zigbee2mqtt/Vibrasjon"))] = str
        schema.update(
            {
                vol.Required("show_bait_age", default=existing.get("show_bait_age", True)): bool,
                vol.Required(
                    "inspection_interval_days", default=existing.get("inspection_interval_days", 0)
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=0, max=3650, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="d"
                    )
                ),
                vol.Required(
                    "inspection_notifications_enabled", default=existing.get("inspection_notifications_enabled", False)
                ): bool,
                vol.Required("override_display", default=bool(existing.get("display"))): bool,
                **self._display_schema(display_settings(options, existing)),
            }
        )
        if kind == "victor":
            for role in SOURCE_SUFFIXES:
                value = existing.get("source_entities", {}).get(role)
                schema[vol.Optional("source_" + role, **({"default": value} if value else {}))] = (
                    selector.EntitySelector()
                )
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
                    vol.Required(
                        "health_notifications_enabled", default=options.get("health_notifications_enabled", False)
                    ): bool,
                    vol.Required(
                        "movement_notifications_enabled", default=options["movement_notifications_enabled"]
                    ): bool,
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
