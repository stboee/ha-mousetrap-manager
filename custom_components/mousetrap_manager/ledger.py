"""Persistent domain model, independent of Home Assistant.

The manager applies changes to a copy, persists it, then publishes the new state.
Event IDs make acknowledgements safe across concurrent clients and restarts.
"""

from copy import deepcopy
from datetime import datetime, timedelta
from uuid import uuid4


class LedgerError(ValueError):
    """An action refers to an invalid or already superseded event."""


def instant(value: str) -> datetime:
    """Read our UTC ISO timestamps, rejecting naive wall-clock values."""
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise LedgerError("Timestamp must include a time zone")
    return result


class Ledger:
    """Authoritative trap state and append-only event journal."""

    def __init__(self, data: dict | None = None):
        self.data = (
            deepcopy(data)
            if data is not None
            else {
                "traps": {},
                "events": [],
                "revision": 0,
            }
        )
        if not isinstance(self.data.get("traps"), dict) or not isinstance(self.data.get("events"), list):
            raise LedgerError("Invalid saved trap register")

    def clone(self):
        return Ledger(self.data)

    def _trap(self, trap_id):
        try:
            return self.data["traps"][trap_id]
        except KeyError as err:
            raise LedgerError("Unknown trap") from err

    def _event(self, event_id):
        for event in self.data["events"]:
            if event["id"] == event_id:
                return event
        raise LedgerError("Unknown event")

    def _append(self, trap_id, kind, at, **extra):
        instant(at)
        event = {"id": uuid4().hex, "trap_id": trap_id, "type": kind, "at": at, **extra}
        self.data["events"].append(event)
        self.data["revision"] += 1
        return event

    def sync_traps(self, configurations, at):
        """Keep stable IDs and historical catches when traps are renamed/archived."""
        changed = False
        configured = {item["id"]: item for item in configurations}
        for trap_id, config in configured.items():
            if trap_id not in self.data["traps"]:
                self.data["traps"][trap_id] = {
                    "id": trap_id,
                    "name": config["name"],
                    "archived": False,
                    "pending_event_id": None,
                    "cooldown_until": None,
                    "last_movement": None,
                }
                self._append(trap_id, "registered", at)
                changed = True
            trap = self._trap(trap_id)
            archived = bool(config.get("archived", False))
            if trap["name"] != config["name"]:
                self._append(trap_id, "renamed", at, old_name=trap["name"], name=config["name"])
                trap["name"] = config["name"]
                changed = True
            if trap["archived"] != archived:
                self._append(trap_id, "archived" if archived else "reactivated", at)
                trap["archived"] = archived
                trap["pending_event_id"] = None
                trap["cooldown_until"] = None
                changed = True
        for trap_id, trap in self.data["traps"].items():
            if trap_id not in configured and not trap["archived"]:
                trap["archived"] = True
                trap["pending_event_id"] = None
                self._append(trap_id, "archived", at)
                changed = True
        return changed

    def movement(self, trap_id, at):
        trap = self._trap(trap_id)
        if trap["archived"] or trap["pending_event_id"]:
            return False
        if trap["cooldown_until"] and instant(at) < instant(trap["cooldown_until"]):
            return False
        event = self._append(trap_id, "movement", at)
        trap["pending_event_id"] = event["id"]
        trap["last_movement"] = at
        trap["cooldown_until"] = None
        return True

    def acknowledge(self, trap_id, event_id, caught, at, cooldown):
        trap = self._trap(trap_id)
        source = self._event(event_id)
        if source["trap_id"] != trap_id or source["type"] != "movement":
            raise LedgerError("Event does not belong to this trap")
        outcome = "capture_confirmed" if caught else "false_alarm"
        previous = [e for e in self.data["events"] if e.get("movement_id") == event_id]
        if previous:
            if previous[0]["type"] == outcome:
                return False  # Identical retry: never count or extend the cooldown twice.
            raise LedgerError("This control event has already been resolved")
        if trap["archived"] or trap["pending_event_id"] != event_id:
            raise LedgerError("This control event is no longer pending")
        self._append(trap_id, outcome, at, movement_id=event_id)
        trap["pending_event_id"] = None
        trap["cooldown_until"] = (instant(at) + timedelta(seconds=cooldown)).isoformat()
        return True

    def catches(self, trap_id=None):
        voided = {e["capture_id"] for e in self.data["events"] if e["type"] == "capture_voided"}
        return [
            e
            for e in self.data["events"]
            if e["type"] == "capture_confirmed"
            and e["id"] not in voided
            and (trap_id is None or e["trap_id"] == trap_id)
        ]

    def undo(self, trap_id, capture_id, at):
        self._trap(trap_id)
        capture = self._event(capture_id)
        if capture["trap_id"] != trap_id or capture["type"] != "capture_confirmed":
            raise LedgerError("Not a capture for this trap")
        if any(e.get("capture_id") == capture_id for e in self.data["events"]):
            return False
        valid = self.catches(trap_id)
        if not valid or valid[-1]["id"] != capture_id:
            raise LedgerError("Only the latest valid capture can be undone")
        self._append(trap_id, "capture_voided", at, capture_id=capture_id)
        return True

    def summary(self, trap_id):
        trap = deepcopy(self._trap(trap_id))
        catches = self.catches(trap_id)
        trap.update(catch_count=len(catches), last_catch=catches[-1]["at"] if catches else None)
        return trap

    def journal(self, trap_id=None, before=None, limit=50):
        events = [e for e in self.data["events"] if trap_id is None or e["trap_id"] == trap_id]
        if before:
            positions = [i for i, e in enumerate(events) if e["id"] == before]
            if not positions:
                raise LedgerError("Unknown journal cursor")
            events = events[: positions[0]]
        events = list(reversed(events[-limit:]))
        return [{**e, "name": self._trap(e["trap_id"])["name"]} for e in events]
