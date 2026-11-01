"""Behavioral tests of the persistent state machine."""

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from custom_components.mousetrap_manager.ledger import Ledger, LedgerError

NOW = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)


def at(seconds=0):
    return (NOW + timedelta(seconds=seconds)).isoformat()


def register():
    ledger = Ledger()
    ledger.sync_traps([{"id": "a", "name": "Loft"}, {"id": "b", "name": "Garasje"}], at())
    return ledger


def confirm(ledger, trap="a", second=1):
    ledger.movement(trap, at(second))
    event = ledger.summary(trap)["pending_event_id"]
    ledger.acknowledge(trap, event, True, at(second + 1), 30)
    return event


def test_movement_is_pending_not_a_catch():
    ledger = register()
    assert ledger.movement("a", at(1))
    pending = ledger.summary("a")["pending_event_id"]
    assert pending and ledger.summary("a")["catch_count"] == 0
    for second in range(2, 100):
        assert not ledger.movement("a", at(second))
    assert len([e for e in ledger.data["events"] if e["type"] == "movement"]) == 1
    assert ledger.summary("b")["pending_event_id"] is None


@pytest.mark.parametrize("caught", [True, False])
def test_retries_across_json_roundtrip_are_idempotent(caught):
    ledger = register()
    ledger.movement("a", at(1))
    pending = ledger.summary("a")["pending_event_id"]
    assert ledger.acknowledge("a", pending, caught, at(2), 30)
    restored = Ledger(json.loads(json.dumps(ledger.data)))
    assert not restored.acknowledge("a", pending, caught, at(3), 30)
    assert restored.summary("a")["catch_count"] == int(caught)
    assert restored.summary("a")["cooldown_until"] == at(32)
    with pytest.raises(LedgerError):
        restored.acknowledge("a", pending, not caught, at(4), 30)


def test_pending_survives_restart_and_movement_is_still_suppressed():
    ledger = register()
    ledger.movement("a", at(1))
    restored = Ledger(json.loads(json.dumps(ledger.data)))
    assert restored.summary("a")["pending_event_id"] == ledger.summary("a")["pending_event_id"]
    assert not restored.movement("a", at(120))


def test_cooldown_survives_restart_and_expires_at_boundary():
    ledger = register()
    confirm(ledger)
    restored = Ledger(json.loads(json.dumps(ledger.data)))
    assert not restored.movement("a", at(31))
    assert restored.movement("a", at(32))
    assert restored.summary("a")["catch_count"] == 1


def test_stale_confirmation_cannot_resolve_a_new_pending_event():
    ledger = register()
    old = confirm(ledger)
    ledger.movement("a", at(40))
    new = ledger.summary("a")["pending_event_id"]
    assert not ledger.acknowledge("a", old, True, at(41), 30)
    assert ledger.summary("a")["pending_event_id"] == new
    assert len(ledger.catches()) == 1


def test_cross_trap_acknowledgement_is_rejected():
    ledger = register()
    ledger.movement("a", at(1))
    with pytest.raises(LedgerError):
        ledger.acknowledge("b", ledger.summary("a")["pending_event_id"], True, at(2), 30)
    assert not ledger.catches()


def test_undo_keeps_history_and_does_not_change_control_state():
    ledger = register()
    confirm(ledger)
    confirm(ledger, second=40)
    old, last = ledger.catches("a")
    ledger.movement("a", at(80))
    pending = ledger.summary("a")["pending_event_id"]
    assert ledger.undo("a", last["id"], at(81))
    assert not ledger.undo("a", last["id"], at(82))
    summary = ledger.summary("a")
    assert summary["catch_count"] == 1
    assert summary["last_catch"] == old["at"]
    assert summary["pending_event_id"] == pending
    assert len([e for e in ledger.data["events"] if e["type"] == "capture_confirmed"]) == 2
    assert len([e for e in ledger.data["events"] if e["type"] == "capture_voided"]) == 1


def test_undo_cannot_remove_an_older_capture_or_a_different_trap():
    ledger = register()
    confirm(ledger)
    first = ledger.catches("a")[-1]["id"]
    confirm(ledger, second=40)
    with pytest.raises(LedgerError):
        ledger.undo("a", first, at(43))
    with pytest.raises(LedgerError):
        ledger.undo("b", first, at(43))


def test_archiving_or_removing_trap_keeps_lifetime_total_and_identity():
    ledger = register()
    confirm(ledger)
    ledger.sync_traps([{"id": "a", "name": "Nytt navn", "archived": True}], at(5))
    assert len(ledger.catches()) == 1
    assert ledger.summary("a")["name"] == "Nytt navn"
    assert ledger.summary("a")["archived"]
    assert ledger.summary("b")["archived"]
    assert not ledger.movement("a", at(200))


def test_undo_to_zero_never_creates_a_negative_counter():
    ledger = register()
    confirm(ledger)
    capture = ledger.catches()[0]
    ledger.undo("a", capture["id"], at(3))
    assert not ledger.undo("a", capture["id"], at(4))
    assert ledger.summary("a")["catch_count"] == 0
    assert ledger.summary("a")["last_catch"] is None


def test_journal_is_paginated_and_filtered_without_omissions():
    ledger = register()
    confirm(ledger, "a")
    confirm(ledger, "b")
    first = ledger.journal(limit=3)
    all_events = list(first)
    while page := ledger.journal(before=all_events[-1]["id"], limit=3):
        all_events.extend(page)
    assert [e["id"] for e in all_events] == [e["id"] for e in reversed(ledger.data["events"])]
    assert all(e["trap_id"] == "a" for e in ledger.journal("a"))


def test_invalid_persistence_is_not_silently_reset():
    with pytest.raises(LedgerError):
        Ledger({"traps": [], "events": []})


def test_upgrade_preserves_old_inspection_time_without_inventing_bait_age():
    ledger = register()
    confirm(ledger)
    data = deepcopy(ledger.data)
    data["events"] = [e for e in data["events"] if e["type"] != "inspection_completed"]
    for trap in data["traps"].values():
        for key in (
            "registered_at",
            "last_inspection",
            "inspection_event_id",
            "last_bait_replaced",
            "bait_event_id",
            "last_sensor_contact",
        ):
            trap.pop(key)
    restored = Ledger(data)
    summary = restored.maintenance("a", at(86403), 1)
    assert summary["last_inspection"] == at(2)
    assert summary["inspection_due"] is True
    assert summary["bait_age_days"] is None
    assert summary["catch_count"] == 1
    assert restored.summary("b")["last_inspection"] is None
    assert len(restored.data["events"]) == len(data["events"])


def test_inspection_covers_bait_without_resetting_its_age():
    ledger = register()
    ledger.replace_bait("a", "initial", at(1))
    assert ledger.inspect("a", "initial", at(86401), 30)
    summary = ledger.maintenance("a", at(86402), 2)
    assert summary["bait_age_days"] == 1
    assert summary["inspection_age_days"] == 0
    assert summary["next_inspection"] == at(259201)
    assert summary["inspection_due"] is False
    assert ledger.maintenance("a", at(259201), 2)["inspection_due"] is True
    assert ledger.maintenance("a", at(259201), 0)["inspection_due"] is False
    assert not ledger.catches()
    assert ledger.data["events"][-1]["bait_inspected"] is True
    restored = Ledger(json.loads(json.dumps(ledger.data)))
    assert restored.maintenance("a", at(259201), 2) == ledger.maintenance("a", at(259201), 2)


@pytest.mark.parametrize("caught", [True, False])
def test_acknowledgement_also_inspects_but_never_changes_bait_age(caught):
    ledger = register()
    ledger.replace_bait("a", "initial", at())
    ledger.movement("a", at(86401))
    pending = ledger.summary("a")["pending_event_id"]
    ledger.acknowledge("a", pending, caught, at(86402), 30)
    summary = ledger.maintenance("a", at(86402), 1)
    assert summary["last_inspection"] == at(86402)
    assert summary["bait_age_days"] == 1
    assert not summary["inspection_due"]
    assert not ledger.acknowledge("a", pending, caught, at(86403), 30)
    assert len([e for e in ledger.data["events"] if e["type"] == "inspection_completed"]) == 1


def test_bait_change_does_not_acknowledge_movement_or_inspection():
    ledger = register()
    ledger.movement("a", at(1))
    pending = ledger.summary("a")["pending_event_id"]
    assert ledger.replace_bait("a", "initial", at(2))
    assert not ledger.replace_bait("a", "initial", at(3))
    assert ledger.summary("a")["last_bait_replaced"] == at(2)
    assert ledger.summary("a")["last_inspection"] is None
    assert ledger.summary("a")["pending_event_id"] == pending
    with pytest.raises(LedgerError):
        ledger.inspect("a", "initial", at(3), 30)
    ledger.acknowledge("a", pending, False, at(4), 30)
    assert ledger.summary("a")["last_inspection"] == at(4)


def test_inspection_retry_and_archiving_cannot_create_extra_events():
    ledger = register()
    assert ledger.inspect("a", "initial", at(1), 30)
    assert not ledger.inspect("a", "initial", at(2), 30)
    assert not ledger.movement("a", at(30))
    token = ledger.summary("a")["inspection_event_id"]
    ledger.sync_traps([{"id": "a", "name": "Loft", "archived": True}], at(3))
    assert not ledger.maintenance("a", at(900000), 1)["inspection_due"]
    with pytest.raises(LedgerError):
        ledger.inspect("a", token, at(4), 30)
    with pytest.raises(LedgerError):
        ledger.replace_bait("a", "initial", at(4))
