"""Server-owned attention reasons and one live overview, independent of notices."""

ATTENTION_DEFAULTS = {
    "title": "Musefeller",
    "navigation_path": "",
    "include_capture": True,
    "include_movement": True,
    "include_inspection": True,
    "include_source_problems": True,
    "include_contact": False,
    "include_battery": False,
}

# Ordered by urgency; a trap can have several reasons but is counted once.
REASONS = (
    ("capture", "include_capture", "Fangst meldt", "#c51f3b", "mdi:rodent"),
    ("movement", "include_movement", "Må kontrolleres", "#986000", "mdi:alert-circle-outline"),
    ("inspection", "include_inspection", "Inspeksjon nødvendig", "#986000", "mdi:clipboard-alert-outline"),
    ("source_unavailable", "include_source_problems", "Kilden er utilgjengelig", "#495465", "mdi:lan-disconnect"),
    ("source_unknown", "include_source_problems", "Kildestatus er ukjent", "#495465", "mdi:help-circle-outline"),
    ("contact_overdue", "include_contact", "Ingen sensorkontakt innen fristen", "#986000", "mdi:access-point-off"),
    ("contact_stale", "include_contact", "Sensorkontakten er gammel", "#986000", "mdi:clock-alert-outline"),
    ("contact_unknown", "include_contact", "Sensorkontakten er ukjent", "#495465", "mdi:help-circle-outline"),
    ("battery", "include_battery", "Lavt batteri", "#986000", "mdi:battery-alert-variant-outline"),
)


def attention_settings(options):
    return {**ATTENTION_DEFAULTS, **options.get("attention", {})}


def valid_navigation_path(value):
    """Only an internal HA path, including optional query/fragment, or no target yet."""
    return isinstance(value, str) and (
        value == ""
        or (
            value.startswith("/")
            and not value.startswith("//")
            and "\\" not in value
            and not any(ord(c) <= 32 or ord(c) == 127 for c in value)
        )
    )


def attention_reasons(options, **facts):
    settings = attention_settings(options)
    return [
        {"code": code, "text": label, "color": color, "icon": icon, "priority": priority}
        for priority, (code, setting, label, color, icon) in enumerate(REASONS)
        if settings[setting] and facts.get(code)
    ]


def attention_overview(manager, now):
    """No imported catches, journal events, or long-term statistics are created."""
    settings = attention_settings(manager.entry.options)
    items = []
    for config in manager.traps:
        # Options can change just before HA reloads the manager; new traps become active after sync.
        if config.get("archived") or config["id"] not in manager.ledger.data["traps"]:
            continue
        summary = manager.summary(config["id"], now)
        if summary["archived"]:
            continue
        view = summary["presentation"]
        reasons = view["attention_reasons"]
        if not reasons:
            continue
        first = reasons[0]
        items.append(
            {
                "trap_id": config["id"],
                "name": summary["name"],
                "location": view["location"],
                "reasons": reasons,
                "reason_text": " · ".join(r["text"] for r in reasons),
                "color": first["color"],
                "icon": first["icon"],
                "priority": first["priority"],
            }
        )
    items.sort(key=lambda item: item["priority"])
    count = len(items)
    return {
        "schema_version": 1,
        "title": settings["title"],
        "count": count,
        "items": items,
        "summary": "Ingen feller trenger tilsyn"
        if not count
        else "1 felle trenger tilsyn"
        if count == 1
        else f"{count} feller trenger tilsyn",
        "navigation_path": settings["navigation_path"],
    }
