"""One central integration with trap registration and admin-only correction."""

from copy import deepcopy
from uuid import uuid4

import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import selector

from .attention import ATTENTION_DEFAULTS, attention_settings, valid_navigation_path
from .const import DEFAULT_COOLDOWN, DOMAIN, SNAP_GRAPHICS
from .ledger import LedgerError
from .notification_preferences import NOTICE_TYPES, notice_default, notice_override
from .presentation import METRIC_LABELS, SOURCE_SUFFIXES, display_settings
from .victor_recovery import RECOVERY_DEFAULTS

THRESHOLDS = {"battery_low": 100, "stale_after_hours": 87600, "offline_after_hours": 87600}
TRAP_LAYOUT = ("show_scene", "metrics")
TRAP_ACTIONS = {
    "pause": "Sett på sesongpause",
    "resume": "Ta i bruk igjen",
    "start_test": "Gjør til testfelle",
    "stop_test": "Ta i ordinær bruk",
    "reset_test": "Nullstill testfelle",
    "remove": "Fjern felle, behold historikk",
    "delete": "Slett felle og historikk",
}


def dropdown(options):
    return selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[{"value": value, "label": label} for value, label in options.items()],
            mode=selector.SelectSelectorMode.DROPDOWN,
        )
    )


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
        options = {
            "traps": [],
            "notifications_enabled": False,
            "cooldown_seconds": DEFAULT_COOLDOWN,
            **deepcopy(dict(self.config_entry.options)),
        }
        manager = self._manager()
        if manager:
            options["traps"] = deepcopy(manager.traps)
        return options

    def _manager(self):
        return self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)

    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["traps", "settings", "cards", "operations"])

    async def async_step_traps(self, user_input=None):
        return self.async_show_menu(step_id="traps", menu_options=["add_trap", "add_victor", "edit_trap", "undo"])

    async def async_step_cards(self, user_input=None):
        return self.async_show_menu(step_id="cards", menu_options=["display", "attention"])

    async def async_step_operations(self, user_input=None):
        return self.async_show_menu(step_id="operations", menu_options=["movement", "thresholds", "victor_recovery"])

    async def async_step_attention(self, user_input=None):
        options = self._options()
        values = attention_settings(options)
        errors = {}
        if user_input is not None:
            values.update(user_input)
            values["title"] = values["title"].strip()
            if not values["title"]:
                errors["title"] = "empty_title"
            if not valid_navigation_path(values["navigation_path"]):
                errors["navigation_path"] = "invalid_navigation_path"
            if not errors:
                options["attention"] = {key: values[key] for key in ATTENTION_DEFAULTS}
                return self.async_create_entry(title="", data=options)
        schema = {
            vol.Required("title", default=values["title"]): str,
            vol.Optional("navigation_path", default=values["navigation_path"]): str,
        }
        for key in ATTENTION_DEFAULTS:
            if key.startswith("include_"):
                schema[vol.Required(key, default=values[key])] = bool
        return self.async_show_form(step_id="attention", data_schema=vol.Schema(schema), errors=errors)

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
            return await self.async_step_trap_menu()
        return self.async_show_form(
            step_id="edit_trap",
            data_schema=vol.Schema(
                {
                    vol.Required("trap_id"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=[{"value": t["id"], "label": self._trap_label(t)} for t in traps],
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_edit_details(self, user_input=None):
        return await self._trap_form("edit_details", user_input, self._editing)

    def _selected_trap(self, options):
        return next((trap for trap in options["traps"] if trap["id"] == self._editing), None)

    def _trap_label(self, config):
        manager = self._manager()
        trap = manager.ledger.data["traps"].get(config["id"], config) if manager else config
        states = []
        if trap.get("archived"):
            states.append("Sesongpause")
        if trap.get("test"):
            states.append("Testfelle")
        return config["name"] + (f" ({', '.join(states)})" if states else "")

    async def async_step_trap_menu(self, user_input=None):
        trap = self._selected_trap(self._options())
        if trap is None:
            return self.async_abort(reason="trap_changed")
        choices = ["edit_details", "trap_notices", "trap_display", "trap_thresholds", "trap_actions"]
        if trap.get("type") == "victor":
            choices.insert(-1, "victor_sources")
        return self.async_show_menu(
            step_id="trap_menu", menu_options=choices, description_placeholders={"trap": self._trap_label(trap)}
        )

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
        schema[vol.Required("show_scene", default=values["show_scene"])] = bool
        schema[vol.Required("metrics", default=values["metrics"])] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                multiple=True, options=[{"value": k, "label": v} for k, v in METRIC_LABELS.items()]
            )
        )
        return schema

    @staticmethod
    def _threshold_schema(values):
        schema = {}
        for key, maximum in THRESHOLDS.items():
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
        if user_input is not None:
            options["display"] = {**options.get("display", {}), **user_input}
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="display", data_schema=vol.Schema(self._display_schema(display_settings(options), True))
        )

    async def _trap_form(self, step_id, user_input, editing=None, kind=None):
        options = self._options()
        existing = next((t for t in options["traps"] if t["id"] == editing), {})
        if editing and not existing:
            return self.async_abort(reason="trap_changed")
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
            if kind == "snap":
                graphic = user_input.get("snap_graphic", existing.get("snap_graphic", "classic"))
                if not isinstance(graphic, str) or graphic not in SNAP_GRAPHICS:
                    errors["snap_graphic"] = "invalid_snap_graphic"
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
            if not errors:
                trap = {**existing, **user_input, "id": editing or uuid4().hex}
                if kind == "victor":
                    trap["type"] = "victor"
                if editing:
                    options["traps"] = [trap if t["id"] == editing else t for t in options["traps"]]
                else:
                    options["traps"].append(trap)
                return self.async_create_entry(title="", data=options)
            existing = {**existing, **user_input}
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
            schema[vol.Required("snap_graphic", default=existing.get("snap_graphic", "classic"))] = (
                selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[{"value": key, "label": value[0]} for key, value in SNAP_GRAPHICS.items()],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            )
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
            }
        )
        if not editing:
            schema[vol.Required("initial_test", default=existing.get("initial_test", False))] = bool
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
                    **{
                        vol.Required(f"{kind}_notifications_enabled", default=notice_default(options, kind)): bool
                        for kind in NOTICE_TYPES
                    },
                }
            ),
        )

    async def async_step_movement(self, user_input=None):
        options = self._options()
        if user_input is not None:
            options["cooldown_seconds"] = int(user_input["cooldown_seconds"])
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="movement",
            data_schema=vol.Schema(
                {
                    vol.Required("cooldown_seconds", default=options["cooldown_seconds"]): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=0, max=600, step=1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s"
                        )
                    ),
                }
            ),
        )

    async def async_step_thresholds(self, user_input=None):
        options = self._options()
        values = display_settings(options)
        errors = {}
        if user_input is not None:
            values.update(user_input)
            errors = self._display_errors(values)
            if not errors:
                options["display"] = {**options.get("display", {}), **user_input}
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id="thresholds", data_schema=vol.Schema(self._threshold_schema(values)), errors=errors
        )

    async def async_step_trap_notices(self, user_input=None):
        options = self._options()
        trap = self._selected_trap(options)
        if trap is None:
            return self.async_abort(reason="trap_changed")
        kinds = [kind for kind in NOTICE_TYPES if kind != "movement" or trap.get("type", "snap") == "snap"]
        if user_input is not None:
            trap["notification_overrides"] = {kind: user_input[kind] for kind in kinds if user_input[kind] != "inherit"}
            trap.pop("inspection_notifications_enabled", None)
            return self.async_create_entry(title="", data=options)
        schema = {}
        for kind in kinds:
            common = "på" if notice_default(options, kind) else "av"
            schema[vol.Required(kind, default=notice_override(trap, kind))] = dropdown(
                {"inherit": f"Følg felles standard ({common})", "on": "På", "off": "Av"}
            )
        return self.async_show_form(
            step_id="trap_notices",
            data_schema=vol.Schema(schema),
            description_placeholders={"master": "på" if options["notifications_enabled"] else "av"},
        )

    async def async_step_trap_display(self, user_input=None):
        return await self._trap_override("trap_display", "trap_display_values", TRAP_LAYOUT, user_input)

    async def async_step_trap_thresholds(self, user_input=None):
        return await self._trap_override("trap_thresholds", "trap_threshold_values", THRESHOLDS, user_input)

    async def _trap_override(self, step, values_step, keys, user_input):
        options = self._options()
        trap = self._selected_trap(options)
        if trap is None:
            return self.async_abort(reason="trap_changed")
        override = trap.get("display", {})
        if user_input is not None:
            if user_input["mode"] == "custom":
                return await getattr(self, f"async_step_{values_step}")()
            trap["display"] = {key: value for key, value in override.items() if key not in keys}
            if not trap["display"]:
                trap.pop("display")
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(
            step_id=step,
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "mode", default="custom" if any(key in override for key in keys) else "inherit"
                    ): dropdown({"inherit": "Følg felles oppsett", "custom": "Egne innstillinger for fellen"}),
                }
            ),
        )

    async def async_step_trap_display_values(self, user_input=None):
        return await self._trap_override_values("trap_display_values", self._display_schema, user_input)

    async def async_step_trap_threshold_values(self, user_input=None):
        return await self._trap_override_values("trap_threshold_values", self._threshold_schema, user_input)

    async def _trap_override_values(self, step, schema, user_input):
        options = self._options()
        trap = self._selected_trap(options)
        if trap is None:
            return self.async_abort(reason="trap_changed")
        values = display_settings(options, trap)
        errors = {}
        if user_input is not None:
            values.update(user_input)
            errors = self._display_errors(values) if step == "trap_threshold_values" else {}
            if not errors:
                trap["display"] = {**trap.get("display", {}), **user_input}
                return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id=step, data_schema=vol.Schema(schema(values)), errors=errors)

    async def async_step_victor_sources(self, user_input=None):
        options = self._options()
        trap = self._selected_trap(options)
        if trap is None or trap.get("type") != "victor":
            return self.async_abort(reason="trap_changed")
        if user_input is not None:
            trap["source_entities"] = {
                role: user_input["source_" + role] for role in SOURCE_SUFFIXES if user_input.get("source_" + role)
            }
            return self.async_create_entry(title="", data=options)
        sources = trap.get("source_entities", {})
        schema = {}
        for role in SOURCE_SUFFIXES:
            value = sources.get(role)
            schema[vol.Optional("source_" + role, **({"default": value} if value else {}))] = selector.EntitySelector()
        return self.async_show_form(step_id="victor_sources", data_schema=vol.Schema(schema))

    async def async_step_trap_actions(self, user_input=None):
        manager = self._manager()
        config = self._selected_trap(self._options())
        if manager is None or config is None or self._editing not in manager.ledger.data["traps"]:
            return self.async_abort(reason="trap_changed")
        trap = manager.ledger.summary(self._editing)
        allowed = ["resume" if trap["archived"] else "pause", "stop_test" if trap["test"] else "start_test"]
        if trap["test"]:
            allowed.append("reset_test")
        allowed.extend(("remove", "delete"))
        if user_input is not None:
            action = user_input["action"]
            if action not in allowed:
                return self.async_abort(reason="trap_changed")
            if trap["pending_event_id"] and action in ("pause", "start_test", "stop_test", "remove"):
                return self.async_abort(reason="pending_control")
            self._trap_action = action
            self._trap_stamp = manager.ledger.management_stamp(self._editing)
            return await self.async_step_trap_action_confirm()
        return self.async_show_form(
            step_id="trap_actions",
            data_schema=vol.Schema({vol.Required("action"): dropdown({key: TRAP_ACTIONS[key] for key in allowed})}),
            description_placeholders={"trap": self._trap_label(config)},
        )

    async def async_step_trap_action_confirm(self, user_input=None):
        manager = self._manager()
        options = self._options()
        config = self._selected_trap(options)
        if (
            manager is None
            or config is None
            or self._editing not in manager.ledger.data["traps"]
            or manager.ledger.management_stamp(self._editing) != self._trap_stamp
        ):
            return self.async_abort(reason="trap_changed")
        action = self._trap_action
        catches = len(manager.ledger.catches(self._editing))
        errors = {}
        if user_input is not None:
            if not user_input.get("confirm"):
                errors["confirm"] = "confirmation_required"
            else:
                choice = {}
                if action == "resume":
                    choice["replace_bait"] = user_input.get("replace_bait", False)
                if action == "start_test":
                    choice["move_history"] = user_input.get("move_history", False)
                try:
                    changed = await manager.async_manage_trap(self._editing, self._trap_stamp, action, **choice)
                except LedgerError:
                    return self.async_abort(reason="trap_changed")
                except OSError:
                    errors["base"] = "save_failed"
                else:
                    if not changed:
                        return self.async_abort(reason="trap_changed")
                    if action in ("remove", "delete"):
                        # Fetch current options again so changes from another form are preserved.
                        return self.async_create_entry(title="", data=self._options())
                    return self.async_abort(reason="trap_action_done")
        schema = {vol.Required("confirm", default=False): bool}
        if action == "resume":
            schema[vol.Required("replace_bait", default=False)] = bool
        if action == "start_test":
            schema[vol.Required("move_history", default=False)] = bool
        impacts = {
            "pause": "Fellen skjules fra kortene. Oppsett og historikk beholdes.",
            "resume": "Klargjør fellen før du bekrefter. Neste inspeksjonsfrist regnes fra i dag.",
            "start_test": f"Fremtidige hendelser går til testloggen. Flytting av tidligere historikk trekker "
            f"{catches} fangster fra samlet klappfelleteller.",
            "stop_test": "Fremtidige hendelser går til driftsloggen. Tidligere tester blir stående i testloggen.",
            "reset_test": "Testfangster, testlogg, ventende kontroll og registrert åte- og inspeksjonsstatus "
            "nullstilles. Oppsett og eventuell tidligere driftshistorikk beholdes.",
            "remove": f"Sensoren kan brukes på en ny felle. Fellens {catches} driftsfangster blir stående i totalen.",
            "delete": f"Fellen og loggen slettes fra integrasjonen. {catches} fangster trekkes fra "
            "samlet klappfelleteller. Historiske verdier i Home Assistant Recorder forblir lagret.",
        }
        return self.async_show_form(
            step_id="trap_action_confirm",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "trap": config["name"],
                "action": TRAP_ACTIONS[action],
                "impact": impacts[action],
            },
        )

    async def async_step_undo(self, user_input=None):
        manager = self._manager()
        if manager is None:
            return self.async_abort(reason="not_loaded")
        choices = []
        for trap_id, trap in manager.ledger.data["traps"].items():
            catches = manager.ledger.catches(trap_id)
            if catches:
                choices.append({"value": trap_id, "label": trap["name"] + (" (fjernet)" if trap["removed"] else "")})
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
