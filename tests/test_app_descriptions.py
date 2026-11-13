"""App-correlated presentation without changing security/event semantics."""
import hashlib
import json

import pytest

from custom_components.lockin_v5.decoder import LockState
from .test_decoder import decoder as decoder, lock_event, NOW


@pytest.mark.parametrize("action,method,side,description", [
    (1, 15, 3, "Door closed report"),
    (2, 15, 1, "Inside-handle opening"),
    (2, 2, 2, "Fingerprint unlock"),
    (2, 5, 2, "Face unlock"),
    (2, 7, 2, "Palm recognition unlock"),
])
def test_app_descriptions_preserve_action_and_dedup(decoder, action, method, side, description):
    payload = lock_event(action=action, method=method, side=side)
    event = decoder.event(payload, NOW)
    assert event.attributes["app_description"] == description
    assert event.event_type == ("locked" if action == 1 else "unlocked")
    assert event.attributes["action"] == ("Locked" if action == 1 else "Unlocked")
    legacy_attrs = {k: v for k, v in event.attributes.items() if k != "app_description"}
    identity = [event.source, event.occurred_at.isoformat(), event.event_type, legacy_attrs]
    legacy_hash = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    assert event.fingerprint == legacy_hash
    state = LockState(decoder, {"seen": [legacy_hash]})
    assert state.apply_event(payload, NOW) is None
    fresh = LockState(decoder)
    assert fresh.apply_event(payload, NOW)
    assert fresh.fields["reported_lock_state"]["value"] == event.attributes["action"]
    assert fresh.fields["lock_activity"]["app_description"] == description
    assert "12345" not in json.dumps(fresh.snapshot())


def test_unmatched_actions_not_given_guessed_app_labels(decoder):
    for action, method, side in ((1, 15, 1), (2, 15, 3), (4, 15, 1), (2, 6, 2)):
        event = decoder.event(lock_event(action=action, method=method, side=side), NOW)
        assert "app_description" not in event.attributes


def test_visitor_wording_preserves_automation_type(decoder):
    payload = {"siid": 7, "eiid": 3, "arguments": [{"piid": 10, "value": int(NOW.timestamp())}]}
    event = decoder.event(payload, NOW)
    assert event.event_type == "passed_by"
    assert event.summary == "Someone appeared at the door"
    identity = [event.source, event.occurred_at.isoformat(), "passed_by", {}]
    assert event.fingerprint == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
