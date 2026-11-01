"""Shared presentation and source references; no Victor API or duplicate counters."""

import math

from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN
from .ledger import instant

DISPLAY_DEFAULTS = {
    "title": "Musefeller",
    "sort": "config",
    "columns": 3,
    "show_summary": True,
    "show_scene": True,
    "animations": True,
    "metrics": ["catches", "present", "last_catch", "battery", "contact", "signal", "bait_age", "inspection_age"],
    "battery_low": 20,
    "stale_after_hours": 24,
    "offline_after_hours": 72,
}
METRIC_LABELS = {
    "catches": "Fangster",
    "present": "Fangst i fellen",
    "last_catch": "Siste fangst",
    "battery": "Batteri",
    "contact": "Siste sensorkontakt",
    "signal": "Signal",
    "bait_age": "Åtealder",
    "inspection_age": "Siden inspeksjon",
}
SOURCE_SUFFIXES = {
    "capture": "capture",
    "present": "kills_present",
    "catches": "total_kills",
    "last_catch": "last_kill_date",
    "contact": "last_report_date",
    "battery": "battery_level",
    "signal": "wireless_network_rssi",
}


def display_settings(options, trap=None):
    result = {**DISPLAY_DEFAULTS, **options.get("display", {})}
    if trap:
        result.update(trap.get("display", {}))
    return result


def source_entities(hass, config):
    """Resolve stable registry identities, including entity renames and disabled sources."""
    registry = er.async_get(hass)
    entries = er.async_entries_for_device(registry, config.get("device_id", ""))
    victor = config.get("type", "snap") == "victor"
    result = {}
    for entity in sorted(entries, key=lambda e: e.entity_id):
        if entity.disabled_by or entity.platform != ("victorsmartkill" if victor else "mqtt"):
            continue
        state = hass.states.get(entity.entity_id)
        if victor:
            for role, suffix in SOURCE_SUFFIXES.items():
                if str(entity.unique_id).endswith("_" + suffix):
                    result.setdefault(role, entity.entity_id)
        else:
            device_class = entity.device_class or entity.original_device_class
            if state:
                device_class = state.attributes.get("device_class", device_class)
            if device_class == "battery" and entity.domain == "sensor":
                result.setdefault("battery", entity.entity_id)
            if device_class == "signal_strength" or "linkquality" in str(entity.unique_id).lower():
                result.setdefault("signal", entity.entity_id)
    # Explicit references are useful when a source integration uses older unique IDs.
    result.update({k: v for k, v in config.get("source_entities", {}).items() if v})
    return result


def source_value(hass, sources, role):
    state = hass.states.get(sources.get(role, ""))
    if state is None or state.state in ("unknown", "unavailable", "") or state.attributes.get("restored"):
        return None
    return state.state


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except TypeError, ValueError:
        return None


def presentation(manager, config, summary, now):
    """All deadlines, status precedence, thresholds and available actions live here."""
    hass = manager.hass
    settings = display_settings(manager.entry.options, config)
    sources = source_entities(hass, config)
    victor = config.get("type", "snap") == "victor"
    contact = summary["last_sensor_contact"]
    if victor:
        # Imported lazily to keep timestamp validation in one place.
        from .manager import sensor_timestamp

        contact = sensor_timestamp(source_value(hass, sources, "contact"), now)
    battery = number(source_value(hass, sources, "battery"))
    low = battery is not None and battery <= settings["battery_low"]
    age = max(0, (now - instant(contact)).total_seconds()) if contact else None
    stale = bool(age is not None and settings["stale_after_hours"] and age >= settings["stale_after_hours"] * 3600)
    old = bool(age is not None and settings["offline_after_hours"] and age >= settings["offline_after_hours"] * 3600)
    states = [hass.states.get(entity_id) for entity_id in sources.values()]
    unavailable = bool(states) and all(s is not None and s.state == "unavailable" for s in states)
    capture = source_value(hass, sources, "capture")
    present = number(source_value(hass, sources, "present"))
    caught = (capture == "on") or (present is not None and present > 0)
    known = capture in ("on", "off") or present is not None
    warnings = []
    if unavailable:
        warnings.append("Kildeintegrasjonen er utilgjengelig")
    if old:
        warnings.append("Ingen sensorkontakt innen fristen")
    elif stale:
        warnings.append("Sensorkontakten er gammel")
    if low:
        warnings.append("Lavt batteri")
    actions = []
    if not victor and summary["pending_event_id"] and not summary["archived"]:
        actions.extend(
            {"service": service, "label": label, "event_id": summary["pending_event_id"]}
            for service, label in (("confirm_catch", "Bekreft fangst"), ("false_alarm", "Falsk alarm"))
        )
    if not summary["archived"] and (victor or not summary["pending_event_id"]):
        actions.append(
            {
                "service": "inspection_completed",
                "label": "Inspeksjon utført",
                "event_id": summary["inspection_event_id"] or "initial",
                "contextual": summary["inspection_due"] or (victor and caught),
            }
        )
    if not summary["archived"] and summary["show_bait_age"]:
        actions.append(
            {
                "service": "bait_replaced",
                "label": "Åte byttet",
                "event_id": summary["bait_event_id"] or "initial",
                "contextual": bool(summary["pending_event_id"] or summary["inspection_due"] or (victor and caught)),
            }
        )
    # An unresolved snap movement remains visible even during a source outage.
    if summary["archived"]:
        status, label, scene, color, priority = "archived", "Arkivert", "unavailable", "#495465", 9
    elif summary["pending_event_id"] and not victor:
        status, label, scene, color, priority = "pending", "Må kontrolleres", "pending", "#986000", 0
    elif unavailable:
        status, label, scene, color, priority = "unavailable", "Utilgjengelig", "unavailable", "#495465", 2
    elif victor and caught:
        status, label, scene, color, priority = "capture", "Fangst meldt", "capture", "#c51f3b", 0
    elif victor and not known:
        status, label, scene, color, priority = "unknown", "Status ukjent", "unavailable", "#495465", 3
    elif summary["inspection_due"]:
        status, label, scene, color, priority = "inspection", "Tid for inspeksjon", "inspection", "#986000", 1
    elif old or stale or low:
        status, label, scene, color, priority = "warning", warnings[0], "normal", "#986000", 2
    else:
        status, label, scene, color, priority = (
            "monitoring",
            "Ingen fangst meldt" if victor else "Overvåking aktiv",
            "normal",
            "#246c47",
            4,
        )
    device = dr.async_get(hass).async_get(config.get("device_id", ""))
    area = ar.async_get(hass).async_get_area(device.area_id) if device and device.area_id else None
    location = config.get("location", "") or (area.name if area else "")
    metrics = []
    for role in settings["metrics"]:
        if role not in METRIC_LABELS or (role == "bait_age" and not summary["show_bait_age"]):
            continue
        metric = {"key": role, "label": METRIC_LABELS[role]}
        if role in ("bait_age", "inspection_age"):
            metric.update(value=summary[role + "_days"], format="days")
        elif not victor and role in ("catches", "last_catch", "contact"):
            metric["value"] = {
                "catches": summary["catch_count"],
                "last_catch": summary["last_catch"],
                "contact": contact,
            }[role]
        elif role in sources:
            metric["entity_id"] = sources[role]
        else:
            continue
        if role in ("last_catch", "contact"):
            metric["format"] = "timestamp"
        own_key = {
            "catches": "catch_count",
            "bait_age": "bait_age_days",
            "inspection_age": "inspection_age_days",
            "contact": "last_sensor_contact",
        }.get(role)
        if own_key and (not victor or role in ("bait_age", "inspection_age")):
            entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{DOMAIN}_{config['id']}_{own_key}")
            if entity_id:
                metric["entity_id"] = entity_id
        metrics.append(metric)
    return {
        "type": "victor" if victor else "snap",
        "name": summary["name"],
        "location": location,
        "status": status,
        "label": label,
        "scene": scene,
        "color": color,
        "priority": priority,
        "warnings": warnings,
        "metrics": metrics,
        "actions": actions,
        "show_scene": settings["show_scene"],
        "animations": settings["animations"],
        "source_entities": sources,
        "last_sensor_contact": contact,
        "health": {"unavailable": unavailable, "old_contact": old, "stale_contact": stale, "low_battery": low},
    }
