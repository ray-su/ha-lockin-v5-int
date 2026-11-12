"""Synthetic edge cases; real-recording replay is a separate tool."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from custom_components.lockin_v5.decoder import Decoder, LockState

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


def lock_event(action=2, at=NOW, method=5, side=2):
    return {"siid": 2, "eiid": 1020, "arguments": [{"piid": 1, "value": side}, {"piid": 2, "value": method}, {"piid": 3, "value": action}, {"piid": 4, "value": 12345}, {"piid": 5, "value": int(at.timestamp())}]}


@pytest.fixture
def decoder():
    return Decoder(json.loads((Path(__file__).resolve().parents[1] / "custom_components/lockin_v5/miot-v2203.json").read_text()))


def test_human_readable_unlock(decoder):
    event = decoder.event(lock_event(), NOW)
    assert event.summary == "Unlocked — face recognition — outside"
    assert event.event_type == "unlocked"
    assert "12345" not in json.dumps(event.attributes)


def test_fingerprint_unlock_does_not_infer_owner(decoder):
    event = decoder.event(lock_event(method=2), NOW)
    assert event.summary == "Unlocked — fingerprint — outside"
    assert event.attributes["method_code"] == 2
    assert event.event_type == "unlocked"
    assert "owner" not in json.dumps(event.attributes).lower()
    assert "12345" not in json.dumps(event.attributes)


def test_palm_method_is_distinct_and_not_overclaimed(decoder):
    event = decoder.event(lock_event(method=7), NOW)
    assert event.summary == "Unlocked — palm recognition — outside"
    assert event.attributes["method_code"] == 7
    assert "fingerprint" not in event.summary
    assert "vein" not in event.summary  # Physical palm-vein mapping still needs a live sample.


@pytest.mark.parametrize("action", range(1, 10))
def test_all_documented_actions(decoder, action):
    event = decoder.event(lock_event(action), NOW)
    assert event and event.event_type != "unrecognized"


def test_unknown_action_not_locked(decoder):
    state = LockState(decoder)
    event = state.apply_event(lock_event(99), NOW)
    assert event.event_type == "unrecognized"
    assert "reported_lock_state" not in state.fields


@pytest.mark.parametrize("bad", [True, None, 1.5, [], {}, "locked", "-1"])
def test_invalid_codes(decoder, bad):
    assert decoder.event(lock_event(bad), NOW) is None


def test_repeated_event_and_restart(decoder):
    state = LockState(decoder)
    assert state.apply_event(lock_event(), NOW)
    assert state.apply_event(lock_event(), NOW + timedelta(minutes=2)) is None
    restored = LockState(decoder, json.loads(json.dumps(state.snapshot())))
    assert restored.apply_event(lock_event(), NOW + timedelta(days=1)) is None
    assert restored.fields["reported_lock_state"]["value"] == "Unlocked"


def test_old_event_cannot_regress_state(decoder):
    state = LockState(decoder)
    state.apply_event(lock_event(1), NOW)
    assert state.apply_event(lock_event(2, NOW - timedelta(seconds=30)), NOW) is None
    assert state.fields["reported_lock_state"]["value"] == "Locked"


def test_same_action_at_new_time_is_new_event(decoder):
    state = LockState(decoder)
    assert state.apply_event(lock_event(1), NOW)
    assert state.apply_event(lock_event(1, NOW + timedelta(seconds=2)), NOW + timedelta(seconds=2))


def test_stuck_door_property_never_overwrites_unlock(decoder):
    state = LockState(decoder)
    state.apply_event(lock_event(), NOW)
    assert state.apply_property({"siid": 3, "piid": 1021, "value": 16}, NOW)
    assert state.fields["door_report"]["value"] == "Locked"
    assert state.fields["reported_lock_state"]["value"] == "Unlocked"


@pytest.mark.parametrize("code,expected", [(23, "Door left open too long"), (24, "Door ajar"), (25, "Door forced open")])
def test_warnings(decoder, code, expected):
    event = decoder.event({"siid": 2, "eiid": 1007, "arguments": [{"piid": 5, "value": int(NOW.timestamp())}, {"piid": 6, "value": code}]}, NOW)
    assert event.summary == expected


def test_missing_future_or_bad_timestamp_rejected(decoder):
    event = lock_event()
    event["arguments"] = event["arguments"][:-1]
    assert decoder.event(event, NOW) is None
    assert decoder.event(lock_event(at=NOW + timedelta(days=1)), NOW) is None
    assert decoder.event(lock_event(at=datetime(1970, 1, 1, tzinfo=timezone.utc)), NOW) is None


def test_duplicate_arguments_rejected(decoder):
    payload = lock_event()
    payload["arguments"].append({"piid": 3, "value": 1})
    assert decoder.event(payload, NOW) is None


def test_private_firmware_message_not_retained(decoder):
    state = LockState(decoder)
    state.apply_event({"siid": 11, "eiid": 3, "arguments": [{"piid": 20, "value": "Face Note private biometric data"}]}, NOW)
    snapshot = json.dumps(state.snapshot())
    assert "biometric" not in snapshot and "Face Note" not in snapshot
    assert state.fields["last_diagnostic"]["value"] == "Unmapped firmware diagnostic received"


def test_untimed_event_short_dedup_not_permanent(decoder):
    state = LockState(decoder)
    payload = {"siid": 11, "eiid": 1, "arguments": []}
    assert state.apply_event(payload, NOW)
    assert state.apply_event(payload, NOW + timedelta(seconds=1)) is None
    assert state.apply_event(payload, NOW + timedelta(seconds=10))


def test_battery_and_presence_labels(decoder):
    state = LockState(decoder)
    for s, p, value in [(4, 1003, 67), (10, 1, 100), (4, 1034, 3)]:
        assert state.apply_property({"siid": s, "piid": p, "value": value}, NOW)
    assert state.fields["battery_presence"]["value"] == "Both batteries installed"
    assert state.fields["battery_a"]["value"] == 67
    assert not state.apply_property({"siid": 4, "piid": 1003, "value": 101}, NOW)
    assert not state.apply_property({"siid": 4, "piid": 1003, "value": 90, "code": -1}, NOW)


def test_dual_service_doorbell_dedup(decoder):
    state = LockState(decoder)
    assert state.apply_event({"siid": 5, "eiid": 1006, "arguments": [{"piid": 1, "value": int(NOW.timestamp())}]}, NOW)
    assert state.apply_event({"siid": 7, "eiid": 1, "arguments": [{"piid": 10, "value": int(NOW.timestamp())}]}, NOW) is None
