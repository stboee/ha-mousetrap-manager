"""Numeric counters and dashboard state, created automatically."""

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import TrapEntity
from .victor_recovery import RECOVERY_STATES


async def async_setup_entry(hass, entry, async_add_entities):
    manager = hass.data[DOMAIN][entry.entry_id]
    entities = [CatchCount(manager), VictorRecoveryStatus(manager), DashboardSettings(manager)]
    for config in manager.traps:
        entities.append(TrapStatus(manager, config))
        if config.get("type", "snap") == "snap":
            entities.append(CatchCount(manager, config["id"]))
        entities.extend(
            MaintenanceSensor(manager, config["id"], key)
            for key in MAINTENANCE_SENSORS
            if config.get("type", "snap") == "snap" or key != "last_sensor_contact"
        )
    async_add_entities(entities)


class CatchCount(TrapEntity, SensorEntity):
    _attr_state_class = SensorStateClass.TOTAL
    _attr_icon = "mdi:rodent"
    _attr_suggested_display_precision = 0

    def __init__(self, manager, trap_id=None):
        super().__init__(manager, trap_id)
        self._attr_unique_id = f"{DOMAIN}_{trap_id or manager.entry.entry_id}_catch_count"
        self._attr_name = "Bekreftede fangster" if trap_id else "Snap-fangster"

    @property
    def native_value(self):
        return len(self.manager.ledger.catches(self.trap_id))

    @property
    def extra_state_attributes(self):
        return {"mousetrap_manager_total": True} if self.trap_id is None else None


class VictorRecoveryStatus(TrapEntity, SensorEntity):
    _attr_translation_key = "victor_recovery"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = RECOVERY_STATES
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:restart-alert"

    def __init__(self, manager):
        super().__init__(manager)
        self._attr_unique_id = f"{DOMAIN}_{manager.entry.entry_id}_victor_recovery"

    @property
    def native_value(self):
        return self.manager.victor_recovery.status

    @property
    def extra_state_attributes(self):
        return self.manager.victor_recovery.attributes


class DashboardSettings(TrapEntity, SensorEntity):
    """One presentation setup, shared by every browser and auto-discovering card."""

    _attr_name = "Kortoppsett"
    _attr_icon = "mdi:view-dashboard-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager):
        super().__init__(manager)
        self._attr_unique_id = f"{DOMAIN}_{manager.entry.entry_id}_dashboard"

    @property
    def native_value(self):
        return self.manager.ledger.data["revision"]

    @property
    def extra_state_attributes(self):
        return {"mousetrap_manager_dashboard": True, "display": self.manager.display}


class TrapStatus(TrapEntity, SensorEntity):
    _attr_icon = "mdi:rodent"
    _attr_name = "Status"

    def __init__(self, manager, config):
        super().__init__(manager, config["id"])
        self.config = config
        self._attr_unique_id = f"{DOMAIN}_{self.trap_id}_status"

    @property
    def native_value(self):
        trap = self.manager.summary(self.trap_id)
        status = trap["presentation"]["status"]
        return {"unavailable": "source_unavailable", "unknown": "source_unknown"}.get(status, status)

    @property
    def extra_state_attributes(self):
        trap = self.manager.summary(self.trap_id)
        attributes = {
            "mousetrap_manager": True,
            "trap_id": self.trap_id,
            "source_device_id": self.config.get("device_id"),
            "trap_name": trap["name"],
            "archived": trap["archived"],
            "presentation": trap["presentation"],
            "pending_event_id": trap["pending_event_id"],
            "catch_count": trap["catch_count"],
            "last_catch": trap["last_catch"],
            "last_movement": trap["last_movement"],
            "cooldown_until": trap["cooldown_until"],
            "revision": self.manager.ledger.data["revision"],
            **{
                key: trap[key]
                for key in (
                    "show_bait_age",
                    "last_bait_replaced",
                    "bait_age_days",
                    "bait_event_id",
                    "last_inspection",
                    "inspection_age_days",
                    "inspection_event_id",
                    "next_inspection",
                    "inspection_due",
                    "inspection_interval_days",
                    "last_sensor_contact",
                )
            },
        }
        if self.config.get("type") == "victor":
            for key in ("catch_count", "last_catch", "last_movement", "last_sensor_contact"):
                attributes.pop(key, None)
        return attributes


MAINTENANCE_SENSORS = {
    "bait_age_days": ("Åtealder", "mdi:cheese", True),
    "last_bait_replaced": ("Åte sist byttet", "mdi:cheese", False),
    "last_inspection": ("Sist inspisert", "mdi:clipboard-check-outline", False),
    "inspection_age_days": ("Tid siden inspeksjon", "mdi:clipboard-clock-outline", True),
    "next_inspection": ("Neste inspeksjon", "mdi:calendar-clock", False),
    "last_sensor_contact": ("Siste sensorkontakt", "mdi:access-point", False),
}


class MaintenanceSensor(TrapEntity, SensorEntity):
    def __init__(self, manager, trap_id, key):
        super().__init__(manager, trap_id)
        self.key = key
        self._attr_name, self._attr_icon, self.is_age = MAINTENANCE_SENSORS[key]
        self._attr_unique_id = f"{DOMAIN}_{trap_id}_{key}"
        if self.is_age:
            self._attr_device_class = SensorDeviceClass.DURATION
            self._attr_native_unit_of_measurement = UnitOfTime.DAYS
            config = next((t for t in manager.traps if t["id"] == trap_id), {})
            if config.get("type", "snap") == "snap":
                self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_suggested_display_precision = 0
        else:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        value = self.manager.summary(self.trap_id)[self.key]
        return value if self.is_age or value is None else datetime.fromisoformat(value)
