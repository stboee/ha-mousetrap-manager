"""Shared defaults and optional per-trap overrides for HA's notification panel."""

NOTICE_TYPES = {
    "movement": "Bevegelse som krever kontroll",
    "inspection": "Inspeksjonsfrist nådd",
    "health": "Batteri eller sensorkontakt",
}


def notice_default(options, kind):
    # Earlier installations enabled movement notices when the master switch was turned on.
    return options.get(f"{kind}_notifications_enabled", kind == "movement")


def notice_override(config, kind):
    value = config.get("notification_overrides", {}).get(kind)
    if value in ("on", "off"):
        return value
    if kind == "inspection" and "inspection_notifications_enabled" in config:
        return "on" if config["inspection_notifications_enabled"] else "off"
    return "inherit"


def notice_enabled(options, config, kind):
    if not options.get("notifications_enabled", False):
        return False
    override = notice_override(config, kind)
    return notice_default(options, kind) if override == "inherit" else override == "on"
